import streamlit as st
import requests
import os
import json
import time
from datetime import datetime

st.set_page_config(page_title="vLLM Nexus", page_icon="🤖", layout="wide")

VLLM_Host = os.environ.get("VLLM_HOST", "http://localhost:8000")


def check_health():
    try:
        response = requests.get(f"{VLLM_Host}/health", timeout=2)
        if response.status_code == 200:
            return "online"
        else:
            return "offline"
    except Exception as e:
        return "offline"

def fetch_models():
    try:
        response = requests.get(f"{VLLM_Host}/v1/models", timeout=3)
        if response.status_code == 200:
            # Extract model IDs from the response
            models= response.json().get("data", [])
            return [model["id"] for model in models]
    except: 
      pass
    return []    

#streaming chat completion: Send a chat request and get back a streaming response
def chat_stream(model_id, messages,temperature,top_p):
    return requests.post(
        f"{VLLM_Host}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json={
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True
        },
        stream=True,timeout=120
    )


#chat parsing: parse the streaming response and yield content as it arrives
#Extract text chunks from Server-Sent Events (SSE) stream
#vLLM sends responses as SSE: data: {"choices":[{"delta":{"content":"Hello"}}]}
def parse_stream(response):
    for line in response.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8")
        if line.startswith("data: "):
              data = line[6:]
              if data == "[DONE]":
                break
              try:
                  delta = json.loads(data)["choices"][0]["delta"]
                  if "content" in delta and delta["content"]:
                      yield delta["content"]
              except Exception:
                  continue

#Session State Management: Persist data across Streamlit reruns (UI updates)
for k,v in {"messages":[],"req_count":0,"total_tokens":0,"last_latency":0.0}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Sidebar controls
with st.sidebar:
    status = check_health()
    models = fetch_models()

    #server status
    if check_health():
        st.success("Server Online")
    else:
        st.error("Server Offline")
    
    st.divider()

    #Model selection
    st.subheader("Models")
    
    if models:
        selected_model = st.selectbox("Select a model", models)
        st.write(f"Selected model: **{selected_model}**")
    else:
        st.warning("No models available.Check for vLLM server status.")
        selected_model = None
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.05)
    top_p = st.slider("Top-p (nucleus sampling)", 0.0, 1.0, 0.95, 0.05)

    #clear chat history
    if st.button("🧹 CLEAR CHAT"):
        st.session_state.messages = []
        st.session_state.req_count = 0
        st.session_state.total_tokens = 0
        st.session_state.last_latency = 0.0
        st.rerun()

    
    #refresh button
    if st.button("🔄 REFRESH"):
        st.rerun()


    c1, c2 = st.columns(2)
    c1.metric("REQS", st.session_state.req_count)
    c2.metric("TOKENS", st.session_state.total_tokens)
    st.metric("LATENCY", f"{st.session_state.last_latency:.2f}s")


# Display all stored messages
for msg in st.session_state.messages:
    role = msg["role"]  # "user" or "assistant"
    content = msg["content"]  # The actual text
    
    with st.chat_message(role):
        st.write(content)
        
        if role == "assistant":
            st.caption(f"{msg.get('latency', '')} · ~{msg.get('tokens', 0)} tokens")

# Get user input
prompt = st.chat_input("Type your message:")

if prompt:
    # Save it to history
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "ts": datetime.now().strftime("%H:%M:%S")
    })
    
    # Show it on screen
    with st.chat_message("user"):
        st.write(prompt)

    if status != "online" or not selected_model:
        st.warning("⚠  vLLM server offline or no model loaded.")
    else:
        api_msgs = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] in ("user", "assistant")]
        with st.chat_message("assistant", avatar="⚡"):
            placeholder = st.empty()
            full = ""
            t0 = time.time()
            try:
                for chunk in parse_stream(chat_stream(selected_model, api_msgs, temperature, top_p)):
                    full += chunk
                    placeholder.write(full + "▌")  # Show the current content with a cursor
                    #placeholder.markdown(f'<div class="abubble">{full}▌</div>', unsafe_allow_html=True)
                latency = round(time.time() - t0, 2)
                toks    = len(full.split())
                ts_r    = datetime.now().strftime("%H:%M:%S")
                placeholder.write(full)  # Final content without cursor
                #placeholder.markdown(f'<div class="abubble">{full}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="meta">{ts_r} · {latency}s · ~{toks} tokens</div>', unsafe_allow_html=True)
                st.session_state.messages.append({"role": "assistant", "content": full, "ts": ts_r, "latency": f"{latency}s", "tokens": toks})
                st.session_state.req_count    += 1
                st.session_state.total_tokens += toks
                st.session_state.last_latency  = latency
            except Exception as e:
                st.error(f"⚠  Stream error: {e}")    



    


