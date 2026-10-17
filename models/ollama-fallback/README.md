# ollama-fallback

Ollama のモデルの置き場（`OLLAMA_MODELS` にこのフォルダを渡す）。memory-search が索引を作るときと、memory-recall が問いを埋め込むときに使う。この公開用の Workspace には本体を置かない。

- 索引の埋め込み: `ollama pull hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q8_0`
- 問いの埋め込み（軽い版）: `ollama pull hf.co/Abiray/Nemotron-3-Embed-8B-GGUF:Q4_K_M`
