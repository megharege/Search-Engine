# Ayurveda Search Engine

A powerful Ayurveda herb and remedy search engine built with MeiliSearch.

## Features
- **Fast Full-Text Search**: Instant search capabilities across Ayurvedic herbs, remedies, and treatments using MeiliSearch.
- **API & Backend**: Python-based API integrating with the MeiliSearch index.
- **Clean & Responsive UI**: User-friendly frontend for browsing the Ayurvedic database.
- **MCP Server Integration**: Seamless integration with the Model Context Protocol (MCP) via the dedicated server.
- **Data Pipeline**: Automated processing and ingestion of Ayurvedic datasets.

## Getting Started

To launch the application locally:
1. Run `Start Ayurveda Explorer.bat` in the root directory.
2. The batch script will automatically initialize the MeiliSearch instance and start the backend/frontend servers.

## Project Structure

- `ayurveda_meili/`: Main search application containing the Python API (`api.py`) and frontend assets in the `public/` folder.
- `Meili MCP Server/`: MCP server integration scripts and configurations.
- `Pipeline/`: Data pipeline scripts for extracting, transforming, and loading (ETL) the Ayurvedic data.
- `Website/`: Additional frontend assets and website resources.
- `Final data/`: The final processed Ayurveda dataset (JSONL/CSV formats) ready for indexing.
- `Start Ayurveda Explorer.bat`: Batch script to easily spin up the environment.

## Contributing
Feel free to open issues or submit pull requests for any enhancements or bug fixes.
