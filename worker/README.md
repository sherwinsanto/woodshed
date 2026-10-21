# Worker

Runs [Demucs](https://github.com/adefossez/demucs) to split an uploaded song into
four stems (vocals, drums, bass, other) and writes them to object storage.

Locally it runs on your own GPU (CUDA) or CPU; in production it runs on Modal's
serverless GPUs. Implementation starts in week 1, see the GitHub Issues.
