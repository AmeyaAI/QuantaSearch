# QuantaSearch
QuantaSearch is a powerful document search library with support for word, excel, pdf and OCR document types.

[![License](https://img.shields.io/github/license/AmeyaAI/QuantaSearch.svg)](https://github.com/AmeyaAI/QuantaSearch/blob/main/LICENSE)  [![Version](https://img.shields.io/github/v/release/AmeyaAI/QuantaSearch.svg)](https://github.com/AmeyaAI/QuantaSearch/releases) ![Python](https://img.shields.io/badge/python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115.5-green)

---

## 📜 About
This project helps users quickly find and retrieve document names containing specific keywords from their uploaded files.
Built with performance and scalability in mind, it streamlines document search by scanning file contents and matching them to user queries, making it ideal for knowledge management, research, and digital archives.

### Key Use Cases:
- **Enterprise Knowledge Management**: Search through company documentation, policies, and procedures
- **Research Databases**: Find relevant research papers and academic documents
- **Legal Document Management**: Quickly locate case files and legal references
- **Content Management Systems**: Search through articles, blogs, and multimedia content


---

## ✨ Features

### Core Features
- ✅ **Multi-format Support**: PDF, DOCX, DOC, TXT, CSV, XLS, XLSX
- ✅ **Dual Search Modes**: 
  - **Partial Matching**: Find documents containing similar terms
  - **Exact Matching**: Precise keyword matching with special character support
- ✅ **Document States**: Draft and Published document management
- ✅ **Version Control**: Multiple document versions with easy switching
- ✅ **Real-time Preview**: Highlighted text snippets showing search context
- ✅ **Scalable Architecture**: Microservices with horizontal scaling
- ✅ **Advanced Caching**: Redis-powered search result caching
- ✅ **Async Processing**: RabbitMQ-based background processing

### Advanced Features
- ✅ **Inverted Index Search**: Lightning-fast text retrieval using custom indexing
- ✅ **BM25L Scoring**: Advanced relevance scoring algorithm
- ✅ **MongoDB Atlas Search**: Vector-based semantic search
- ✅ **Text Preprocessing**: NLP-based text cleaning and processing




---

## 🏗 Tech Stack

### Backend Framework
- **FastAPI** 0.115.5 - High-performance async web framework
- **Python** 3.9+ - Core programming language
- **LlamaIndex** 0.12.17 - Orchestrate document indexing, retrieval, and keyword/phrase search

### Databases & Storage
- **MongoDB** 4.11.1 - Document database with vector search capabilities
- **Redis** 5.2.1 - In-memory caching and session storage

### Message Queue & Processing
- **RabbitMQ** (aio-pika 9.5.4) - Async message queuing
- **Asyncio** - Asynchronous processing framework

### Document Processing
- **EasyOCR** – Optical Character Recognition for extracting text from images.

- **Ameya DataProcessing** – Custom document parsing library with specialized extractors:

    - **PDF Extractor** – Parses and extracts text from PDF files.

    - **DOC Extractor** – Parses and extracts text from DOC and DOCX files.

    - **Excel Extractor** – Parses and extracts data from XLS and XLSX files.

    - **CSV Extractor** – Parses and processes CSV files.

    - **TXT Extractor** – Parses and processes plain text files.

- **NLTK** – Natural Language Toolkit for text preprocessing and NLP tasks.

- **Fast Inverted Index** – High-performance indexing engine for keyword search.

---

## 🛠 Installation

### Prerequisites
- Python >= 3.9
- Docker (see [Docker installation guide](https://docs.docker.com/engine/install/))
- MongoDB (local or cloud instance)

### ⚙ Configuration
Set environment variables before running:
#### Environment Variables

| Variable | Description |  Required |
|----------|-------------|----------|
| `MONGODB_URI` | MongoDB connection string | ✅ |

Or create a `.env` file:
```
# MongoDB connection string format:
# SRV: mongodb+srv://username:password@cluster-host
MONGODB_URI= <SRV foramt uri>
```

For detailed environment variable descriptions, default values, and advanced configuration examples, see the [Docusaurus Configuration Documentation]().


### Clone & Run with Docker Compose

```bash
# Clone the repository
git clone https://github.com/AmeyaAI/QuantaSearch
cd QuantaSearch
```
### Build and Start Services
```bash
docker compose up -d --build
```
This command builds the images (if needed) and starts all services in detached mode.

### Force a Fresh Build (no cache)
```bash
docker compose build --no-cache && docker compose up -d
```
Use this if you’ve changed dependencies (e.g., `requirements.txt`) or want to ensure a completely clean build.

### Stop and Remove Services
```bash
docker compose down
```
This stops all running containers and removes them (but keeps volumes and networks unless specified otherwise).


➡ For full installation steps (including Docker setup for Linux, Windows, and macOS), see our [Docusaurus Installation Guide]().

---

## 🚀 Usage
Example:

#### Upload Publish document
```python
import requests
import json

BASE_URL = "http://localhost:4455/quantasearch/v1"
headers = {"Content-Type": "application/json"}

upload_data = {
    "document_download_url": "https://s3.amazonaws.com/bucket/research_paper.pdf",
    "user_id": "researcher_001",
    "realm": {"department": "AI_Research"},
    "document_id": "paper_001",
    "version_id": 1,
    "published_date": "2025-01-15T10:00:00Z"
}

response = requests.post(f"{BASE_URL}/user/upload_publish", 
                        json=upload_data, headers=headers)
print(f"Upload Status: {response.json()}")

```

#### Check upload status
```python
import requests
import json

BASE_URL = "http://localhost:4455/quantasearch/v1"
headers = {"Content-Type": "application/json"}

status_response = requests.get(f"{BASE_URL}/user/file_upload_status_check", 
                              params={"user_id": "researcher_001", 
                                     "document_id": "paper_001"})
print(f"Processing Status: {status_response.json()}")

```

#### Search documents
```python
import requests
import json

BASE_URL = "http://localhost:4455/quantasearch/v1"
headers = {"Content-Type": "application/json"}

search_data = {
    "query": "neural networks deep learning",
    "realm": {"department": "AI_Research"},
    "user_id": "researcher_001",
    "state": "Publish",
    "exact_match": False # If `True` enables exact matching
}

search_response = requests.post(f"{BASE_URL}/user/search", 
                               json=search_data, headers=headers)
results = search_response.json()

print(f"Found {len(results.get('result', []))} documents:")
for doc in results.get('result', []):
    print(f"- {doc['document_name']} (Score: {doc['relevance_score']})")
```


#### Get detailed preview

```python
import requests
import json

BASE_URL = "http://localhost:4455/quantasearch/v1"
headers = {"Content-Type": "application/json"}

preview_data = {
    "query": "neural networks",
    "realm": {"department": "AI_Research"},
    "user_id": "researcher_001",
    "document_id": "paper_001",
    "state": "Publish"
}

preview_response = requests.post(f"{BASE_URL}/user/search_preview", 
                                json=preview_data, headers=headers)
preview = preview_response.json()

print(f"\nPreview ({preview.get('preview_count')} matches):")
for page in preview.get('preview', []):
    print(f"Page {page['page_no']}:")
    for snippet in page['previews']:
        print(f"  - {snippet}")

```
~~~
~~~

> ⚠️ **Important Note**  
> The folder named **`ameya-inverted-index`** is critical for the system as it stores all indexes for uploaded files.  
> 
> - **Do not delete or remove this folder.**  
> - Always ensure that the folder path is mounted as a **Docker volume** so that data is persisted across container restarts.  
> - If you change the folder path, remember to update the corresponding path in the **`docker-compose.yml`** file to maintain consistency.


For complete API reference and advanced examples, see our [Docusaurus Documentation]().

---

## 📡 API / Endpoints
| Method | Endpoint         | Description         |
|--------|------------------|---------------------|
| GET    | `/quantasearch/v1/user/file_upload_status_check`    | Check the processing status of uploaded documents.|
| GET    | `/quantasearch/v1/platform/get_document_count_meta` | Get aggregated statistics about user documents.|
| POST   | `/quantasearch/v1/user/upload_draft`     | Upload documents in draft state for processing without making them searchable.|
| POST   | `/quantasearch/v1/user/upload_publish`     | Upload and immediately publish documents for searching.|
| POST   | `/quantasearch/v1/user/search`     | Search through published documents with customizable matching modes.|
| POST   | `/quantasearch/v1/user/search_preview`     | Get detailed preview of search matches within a specific document.|
| POST   | `/quantasearch/v1/user/revert_published_version`     | Change the active version of a published document.|
| POST   | `/quantasearch/v1/user/archive_document`     | Archive or delete documents and their versions.|
| POST   | `/quantasearch/v1/platform/list_files`     | Retrieve all documents for a user with filtering options.|

For complete API reference and examples, see our [Docusaurus Documentation]().

---

## 🤝 Contributing
We welcome contributions!  
1. Fork the repo  
2. Create a feature branch (`git checkout -b feature-name`)  
3. Commit changes (`git commit -m 'Add feature'`)  
4. Push to branch (`git push origin feature-name`)  
5. Open a Pull Request  

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📄 License
This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for more details.

---

## 🙏 Credits
- [RabbitMQ](https://www.rabbitmq.com/) - Message Broker
- [Redis](https://redis.io/) - In-memory Data Store
- [MongoDB](https://www.mongodb.com/) - Database
- [Fast-inverted-index](https://github.com/lakshminarasimmanv/fast-inverted-index-docs) - High-performance Indexing Engine
- [EasyOCR](https://github.com/JaidedAI/EasyOCR?tab=readme-ov-file) - Optical Character Recognition Engine
---
