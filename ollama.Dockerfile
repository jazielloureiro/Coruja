FROM ollama/ollama:0.5.7

RUN <<EOF
ollama serve &

ollama_pid=$!

sleep 5

ollama pull nomic-embed-text

ollama pull llama3.2:3b

kill -KILL $ollama_pid
EOF