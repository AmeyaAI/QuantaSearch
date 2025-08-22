# Contributing to QuantaSearch

Thank you for your interest in contributing to this Quantasearch platform! This guide will help you get started with contributing to the project.

## 📋 Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Architecture](#project-architecture)
- [Contributing Guidelines](#contributing-guidelines)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Issue Reporting](#issue-reporting)
- [Documentation](#documentation)

## 🤝 Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

## 🚀 Getting Started

### Prerequisites

Before contributing, ensure you have:
- Python >= 3.10
- Docker and Docker Compose
- Git
- A MongoDB Atlas account (for database features)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/AmeyaAI/QuantaSearch
   cd QuantaSearch
   ```

2. **Environment Setup**
   ```bash
   # Copy environment template
   cp env.example .env
   
   # Edit .env with your configuration
   # Required: MONGODB_URI
   ```

3. **Run with Docker Compose**
   ```bash
   docker compose up -d
   ```

4. **Verify Installation**
   ```bash
   curl http://localhost:4455/quantasearch/v1/user/file_upload_status_check
   ```

## 🏗 Project Architecture

### Core Components

- **FastAPI Backend**: Main API service handling document operations
- **Document Processing**: Multi-format support (PDF, DOCX, CSV, TXT, XLS, XLSX)
- **Search Engine**: Dual-mode search with inverted indexing and BM25L scoring
- **Message Queue**: RabbitMQ for async document processing
- **Caching Layer**: Redis for search result optimization
- **Database**: MongoDB with vector search capabilities

### Key Technologies

- **Backend**: Python 3.10+, FastAPI 0.115.5
- **Document Processing**: EasyOCR, Ameya DataProcessing, NLTK
- **Search**: LlamaIndex 0.12.17, Fast Inverted Index
- **Infrastructure**: MongoDB, Redis, RabbitMQ, Docker

## 📝 Contributing Guidelines

### What We're Looking For

- **Bug Fixes**: Issues with document processing, search accuracy, or API responses
- **Performance Improvements**: Optimization of search algorithms, caching, or indexing
- **New Document Formats**: Additional extractors for document types
- **Search Enhancements**: Improved relevance scoring or search modes
- **Infrastructure**: Docker, deployment, or monitoring improvements
- **Documentation**: API documentation, setup guides, or code comments

### Areas for Contribution

1. **Document Extractors**: Support for new file formats
2. **Search Algorithms**: Enhanced relevance scoring or fuzzy matching
3. **Performance**: Caching strategies, database optimization
4. **API Features**: New endpoints or enhanced existing ones
5. **Testing**: Unit tests, integration tests, performance tests
6. **DevOps**: CI/CD pipelines, monitoring, logging



## 📐 Code Style

### Python Standards

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Maximum line length: 88 characters (Black formatter)
- Use meaningful variable and function names

### Code Formatting

```bash
# Install formatting tools
pip install black isort flake8

# Format code
black .
isort .

# Lint code
flake8 .
```

### Documentation Standards

- Document all public functions and classes
- Use descriptive docstrings with parameter and return type information
- Update API documentation for endpoint changes
- Include usage examples for new features

## 🚀 Submitting Changes

### Branch Strategy

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/document-extractor-pptx
   ```

2. **Make Changes**
   - Write code following style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add PowerPoint document extractor
   
   - Add PPTX support to document processing
   - Implement slide text extraction
   - Add unit tests for PowerPoint extractor
   - Update API documentation"
   ```

4. **Push and Create PR**
   ```bash
   git push origin feature/document-extractor-pptx
   ```

### Pull Request Guidelines

- **Title**: Clear, descriptive title using conventional commits format
- **Description**: Explain what changed and why
- **Testing**: Include test results and screenshots if applicable
- **Documentation**: Update relevant documentation
- **Breaking Changes**: Clearly mark any breaking changes

### PR Review Process

1. Automated checks (linting, tests, security)
2. Code review by maintainers
3. Address feedback and update PR
4. Final approval and merge

## 🐛 Issue Reporting

### Bug Reports

Include:
- Steps to reproduce
- Expected vs actual behavior
- Environment details (Python version, OS, Docker version)
- Logs and error messages
- Sample documents (if relevant)

### Feature Requests

Include:
- Clear description of the feature
- Use cases and benefits
- Possible implementation approach
- Examples of similar features

### Issue Labels

- `bug`: Something isn't working
- `enhancement`: New feature or improvement
- `documentation`: Documentation improvements
- `performance`: Performance-related issues
- `good first issue`: Good for newcomers

## 📚 Documentation

### API Documentation

- Follow OpenAPI 3.0 standards
- Include request/response examples
- Document error codes and responses
- Update Docusaurus documentation

### Code Documentation

- Document complex algorithms and business logic
- Explain configuration options
- Provide setup and deployment guides
- Include performance considerations

## 🎯 Development Workflow

### Local Development

1. Use feature branches for all changes
2. Test locally before pushing
3. Run linting and formatting tools
4. Update tests and documentation

### Performance Considerations

- Monitor search query performance
- Optimize document processing pipelines
- Consider memory usage for large documents
- Test with realistic document volumes

### Security Guidelines

- Validate all user inputs
- Sanitize file uploads
- Use environment variables for secrets
- Follow secure coding practices

## 📞 Getting Help

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Create issues for bugs and feature requests  
- **Documentation**: Check existing documentation first
- **Community**: Join our community channels (if available)

## 🏆 Recognition

Contributors will be recognized in:
- README credits section
- Release notes for significant contributions
- GitHub contributor listings

---

<<<<<<< HEAD
Thank you for contributing to the QuantaSearch Service! Your contributions help make document search and retrieval better for everyone. 🚀
=======
Thank you for contributing to the QuantaSearch. Your contributions help make document search and retrieval better for everyone. 🚀
>>>>>>> 33c348e (Updated CONTRIBUTING.md file)
