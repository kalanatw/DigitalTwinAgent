# Intelligent CSV Processing Feature

## Overview
This feature adds intelligent CSV file processing to the Digital Twin application. The system can now analyze any uploaded CSV file, infer its schema and data types, detect time series data, and integrate with the agent pipeline to answer natural language queries about the data.

## Implemented Components

1. **Models**
   - Added TimeSeriesData and TimeSeriesPoint models
   - Updated Document model to include CSV as a file type
   - (CSVDocument, CSVDataset, and CSVColumn models were already implemented)

2. **CSV Processing**
   - CSVProcessor class with intelligent CSV loading, schema inference, and time-series detection
   - Integration with the DocumentProcessor for CSV file handling

3. **API Endpoints**
   - `/api/csv/upload/` - Upload and process CSV files
   - `/api/csv/documents/` - List available CSV documents
   - `/api/csv/documents/<uuid>/` - Get details of a specific CSV document
   - `/api/csv/documents/<uuid>/query/` - Query a CSV document with natural language

4. **Agent Integration**
   - Added `query_csv_data` tool for the agent to query CSV documents
   - Updated agent configuration to include the CSV query tool

5. **UI**
   - Added CSV manager page at `/csv/` with UI for:
     - Uploading CSV files
     - Viewing CSV schema and metadata
     - Querying CSV data using natural language

6. **Testing**
   - Added test cases for CSV processing and API endpoints

## Usage

1. **Upload a CSV File**
   - Navigate to `/csv/` in the application
   - Upload a CSV file using the provided form
   - The system will automatically analyze the file and display its metadata

2. **Query the Data**
   - After uploading, enter a natural language query in the query box
   - Examples: "Show me statistics for this CSV", "What are the trends over time?", "Which column has the highest values?"

3. **Agent Integration**
   - In the chat interface, you can ask the agent about your CSV data
   - Example: "What's in the sales.csv file I uploaded?", "Show me the average temperature over time"

## Technical Implementation

- Intelligent CSV loading with automatic detection of delimiters and encodings
- Schema inference including data types, primary keys, and relationships
- Time series detection for temporal data
- Statistical summary generation for numerical and categorical data
- Integration with the agent pipeline for natural language queries

## Next Steps

1. **Enhance Query Capabilities**
   - Add more advanced query processing
   - Implement data visualization based on query results

2. **Optimize Performance**
   - Add pagination and streaming for large CSV files
   - Implement caching for frequent queries

3. **Improve UI**
   - Add more visualizations and charts
   - Enhance the query interface with suggestions
