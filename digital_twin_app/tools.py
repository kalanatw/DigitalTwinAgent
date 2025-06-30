"""
Tools for the Digital Twin Agent
"""
import random
import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from agents import function_tool

logger = logging.getLogger(__name__)


@function_tool
def sensor_data_tool(sensor_type: str = "all", location: str = "main_facility") -> str:
    """
    Retrieves current sensor data from the digital twin environment.
    
    Args:
        sensor_type: Type of sensor data to retrieve (temperature, pressure, humidity, 
                    vibration, power_consumption, flow_rate, or "all" for all sensors)
        location: Location of the sensors (main_facility, secondary_unit, warehouse)
        
    Returns:
        JSON string containing sensor readings with metadata
    """
    logger.info(f"SensorDataTool called - sensor_type: {sensor_type}, location: {location}")
    
    # Define sensor ranges based on location and type
    sensor_ranges = {
        "main_facility": {
            "temperature": (18.0, 32.0),
            "pressure": (990, 1020),
            "humidity": (30, 80),
            "vibration": (0, 100),
            "power_consumption": (50, 200),
            "flow_rate": (10, 50)
        },
        "secondary_unit": {
            "temperature": (20.0, 28.0),
            "pressure": (995, 1015),
            "humidity": (35, 75),
            "vibration": (0, 80),
            "power_consumption": (30, 150),
            "flow_rate": (5, 30)
        },
        "warehouse": {
            "temperature": (15.0, 25.0),
            "pressure": (1000, 1010),
            "humidity": (40, 70),
            "vibration": (0, 50),
            "power_consumption": (20, 100),
            "flow_rate": (2, 15)
        }
    }
    
    # Get the appropriate ranges for the location
    ranges = sensor_ranges.get(location, sensor_ranges["main_facility"])
    
    # Generate realistic sensor data
    current_time = datetime.now(timezone.utc).isoformat()
    
    all_sensor_data = {
        "temperature": {
            "value": round(random.uniform(*ranges["temperature"]), 1),
            "unit": "°C",
            "status": "normal" if random.random() > 0.1 else "warning",
            "last_calibrated": "2024-01-15T10:30:00Z"
        },
        "pressure": {
            "value": round(random.uniform(*ranges["pressure"]), 1),
            "unit": "hPa",
            "status": "normal" if random.random() > 0.05 else "alert",
            "last_calibrated": "2024-01-10T14:20:00Z"
        },
        "humidity": {
            "value": round(random.uniform(*ranges["humidity"]), 1),
            "unit": "%",
            "status": "normal",
            "last_calibrated": "2024-01-12T09:15:00Z"
        },
        "vibration": {
            "value": round(random.uniform(*ranges["vibration"]), 2),
            "unit": "Hz",
            "status": "normal" if random.random() > 0.15 else "warning",
            "last_calibrated": "2024-01-08T16:45:00Z"
        },
        "power_consumption": {
            "value": round(random.uniform(*ranges["power_consumption"]), 2),
            "unit": "kW",
            "status": "normal",
            "last_calibrated": "2024-01-20T11:00:00Z"
        },
        "flow_rate": {
            "value": round(random.uniform(*ranges["flow_rate"]), 2),
            "unit": "L/min",
            "status": "normal" if random.random() > 0.08 else "warning",
            "last_calibrated": "2024-01-18T13:30:00Z"
        }
    }
    
    # Prepare response data
    response_data = {
        "location": location,
        "timestamp": current_time,
        "sensors": {}
    }
    
    if sensor_type.lower() == "all":
        response_data["sensors"] = all_sensor_data
        logger.info(f"Returning all sensor data for location: {location}")
    elif sensor_type.lower() in all_sensor_data:
        response_data["sensors"] = {sensor_type.lower(): all_sensor_data[sensor_type.lower()]}
        logger.info(f"Returning {sensor_type} data for location: {location}")
    else:
        # Return error for invalid sensor type
        available_sensors = list(all_sensor_data.keys())
        error_response = {
            "error": f"Invalid sensor type: {sensor_type}",
            "available_sensors": available_sensors,
            "location": location,
            "timestamp": current_time
        }
        logger.warning(f"Invalid sensor type requested: {sensor_type}")
        return json.dumps(error_response, indent=2)
    
    return json.dumps(response_data, indent=2)


@function_tool
def system_status_tool(system_component: str = "all") -> str:
    """
    Retrieves the operational status of digital twin system components.
    
    Args:
        system_component: Component to check (motors, pumps, controllers, network, or "all")
        
    Returns:
        JSON string containing system status information
    """
    logger.info(f"SystemStatusTool called for component: {system_component}")
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    system_components = {
        "motors": {
            "motor_1": {"status": "running", "rpm": random.randint(1800, 3600), "temperature": round(random.uniform(40, 80), 1)},
            "motor_2": {"status": "running", "rpm": random.randint(1500, 3200), "temperature": round(random.uniform(35, 75), 1)},
            "motor_3": {"status": "idle", "rpm": 0, "temperature": round(random.uniform(20, 30), 1)}
        },
        "pumps": {
            "pump_a": {"status": "active", "flow_rate": round(random.uniform(15, 45), 2), "pressure": round(random.uniform(2.5, 4.0), 1)},
            "pump_b": {"status": "active", "flow_rate": round(random.uniform(20, 50), 2), "pressure": round(random.uniform(3.0, 4.5), 1)},
            "pump_c": {"status": "maintenance", "flow_rate": 0, "pressure": 0}
        },
        "controllers": {
            "plc_1": {"status": "online", "cpu_usage": random.randint(15, 85), "memory_usage": random.randint(30, 70)},
            "plc_2": {"status": "online", "cpu_usage": random.randint(20, 90), "memory_usage": random.randint(25, 65)},
            "hmi_panel": {"status": "online", "response_time": round(random.uniform(50, 200), 1)}
        },
        "network": {
            "main_switch": {"status": "online", "port_utilization": random.randint(40, 80)},
            "wireless_ap": {"status": "online", "connected_devices": random.randint(5, 15)},
            "firewall": {"status": "active", "threats_blocked": random.randint(0, 5)}
        }
    }
    
    response_data = {
        "timestamp": current_time,
        "components": {}
    }
    
    if system_component.lower() == "all":
        response_data["components"] = system_components
        logger.info("Returning status for all system components")
    elif system_component.lower() in system_components:
        response_data["components"] = {system_component.lower(): system_components[system_component.lower()]}
        logger.info(f"Returning status for {system_component}")
    else:
        available_components = list(system_components.keys())
        error_response = {
            "error": f"Invalid system component: {system_component}",
            "available_components": available_components,
            "timestamp": current_time
        }
        logger.warning(f"Invalid system component requested: {system_component}")
        return json.dumps(error_response, indent=2)
    
    return json.dumps(response_data, indent=2)


@function_tool
def query_csv_data(query: str, document_id: str = None) -> str:
    """
    Query CSV data using natural language.
    
    This tool allows you to ask questions about CSV files that have been uploaded to the system.
    The agent will interpret your query, extract relevant information from the CSV data,
    and provide a response that might include summary statistics, charts, or specific data points.
    
    Args:
        query: Natural language query about the CSV data (e.g. "What's the average temperature?",
              "Show me sales trends over time", "Which product had the highest revenue?")
        document_id: Optional ID of a specific CSV document to query. If not provided,
                    the query will be run against all available CSV documents.
                    
    Returns:
        Response to the query, which may include data summaries, charts, or specific answers
    """
    from .models import CSVDocument, CSVDataset, CSVColumn
    import pandas as pd
    import matplotlib.pyplot as plt
    import io
    import base64
    from django.conf import settings
    import os
    
    logger.info(f"CSV Query Tool called - query: {query}, document_id: {document_id}")
    
    try:
        # If document_id is provided, load that specific document
        if document_id:
            try:
                document = CSVDocument.objects.get(id=document_id)
                return _process_csv_query(query, document)
            except CSVDocument.DoesNotExist:
                return json.dumps({
                    "error": f"CSV document with ID {document_id} not found"
                })
        
        # Otherwise, find the most relevant document(s) for the query
        # For now, just get the most recent document
        documents = CSVDocument.objects.filter(status='completed').order_by('-uploaded_at')
        
        if not documents:
            return json.dumps({
                "error": "No CSV documents available. Please upload a CSV file first."
            })
        
        # Use the most recent document
        document = documents.first()
        return _process_csv_query(query, document)
    
    except Exception as e:
        logger.error(f"Error in CSV query tool: {str(e)}")
        return json.dumps({
            "error": f"Error processing CSV query: {str(e)}"
        })


def _process_csv_query(query: str, document: 'CSVDocument') -> str:
    """
    Process a natural language query against a CSV document.
    
    Args:
        query: The natural language query
        document: The CSVDocument object to query against
        
    Returns:
        JSON string with the query results
    """
    try:
        from django.core.files.storage import default_storage
        import pandas as pd
        import matplotlib.pyplot as plt
        import io
        import base64
        from django.conf import settings
        import os
        
        # Load the dataset and schema information
        dataset = document.dataset
        columns = dataset.columns.all()
        
        # Get the file path
        file_path = document.file_path
        
        # If the file is stored with Django's storage system, get the actual path
        if default_storage.exists(file_path):
            file_path = default_storage.path(file_path)
        
        # Load the CSV file
        # First try pandas auto-detection
        try:
            df = pd.read_csv(file_path)
        except:
            # Try different encodings and separators if that fails
            encodings = ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']
            separators = [',', ';', '\t', '|']
            
            for encoding in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                        break
                    except:
                        continue
        
        # Process different types of queries
        response = {}
        
        # Add metadata about the document
        response["document"] = {
            "title": document.title,
            "rows": document.row_count,
            "columns": document.column_count,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None
        }
        
        # Basic statistics query
        if any(keyword in query.lower() for keyword in ['statistics', 'stats', 'summary', 'describe']):
            # Get numerical columns
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if num_cols:
                # Calculate statistics
                stats = df[num_cols].describe().to_dict()
                response["statistics"] = stats
                response["message"] = f"Here are the statistics for numerical columns in {document.title}"
            else:
                response["message"] = f"No numerical columns found in {document.title}"
        
        # Time series query
        elif any(keyword in query.lower() for keyword in ['time', 'trend', 'over time', 'series']):
            # Check if there are time series defined for this document
            time_series = document.time_series.all()
            
            if time_series.exists():
                ts_data = []
                for ts in time_series[:3]:  # Limit to 3 time series
                    # Get sample points
                    points = ts.points.order_by('timestamp')[:100]  # Limit to 100 points
                    
                    ts_info = {
                        "name": ts.title,
                        "unit": ts.unit,
                        "points": [
                            {"timestamp": p.timestamp.isoformat(), "value": p.value} 
                            for p in points
                        ]
                    }
                    ts_data.append(ts_info)
                
                response["time_series"] = ts_data
                response["message"] = f"Found {time_series.count()} time series in {document.title}"
            else:
                # Try to identify date columns
                date_cols = []
                for col in df.columns:
                    try:
                        pd.to_datetime(df[col])
                        date_cols.append(col)
                    except:
                        continue
                
                if date_cols:
                    response["potential_time_columns"] = date_cols
                    response["message"] = f"No time series defined yet, but found potential date columns: {', '.join(date_cols)}"
                else:
                    response["message"] = "No time series or date columns found in this document"
        
        # Column info query
        elif any(keyword in query.lower() for keyword in ['columns', 'fields', 'attributes']):
            cols_info = []
            for col in columns:
                col_info = {
                    "name": col.name,
                    "type": col.data_type,
                    "description": col.description,
                    "is_numerical": col.is_numerical,
                    "is_categorical": col.is_categorical,
                    "is_time_column": col.is_time_column
                }
                cols_info.append(col_info)
            
            response["columns"] = cols_info
            response["message"] = f"This document has {len(cols_info)} columns"
        
        # Default: sample data
        else:
            # Get a sample of the data (first 10 rows)
            sample_data = df.head(10).to_dict(orient='records')
            response["sample_data"] = sample_data
            response["message"] = f"Here's a sample of data from {document.title}"
        
        return json.dumps(response)
    
    except Exception as e:
        logger.error(f"Error processing CSV query: {str(e)}")
        return json.dumps({
            "error": f"Error processing query: {str(e)}"
        })


# Helper functions for direct API calls (without tool wrapper)
def _get_sensor_data(sensor_type: str = "all", location: str = "main_facility") -> str:
    """Direct function to get sensor data without tool wrapper."""
    logger.info(f"Direct API call - sensor_type: {sensor_type}, location: {location}")
    
    # Define sensor ranges based on location and type
    sensor_ranges = {
        "main_facility": {
            "temperature": (18.0, 32.0),
            "pressure": (990, 1020),
            "humidity": (30, 80),
            "vibration": (0, 100),
            "power_consumption": (50, 200),
            "flow_rate": (10, 50)
        },
        "secondary_unit": {
            "temperature": (20.0, 28.0),
            "pressure": (995, 1015),
            "humidity": (35, 75),
            "vibration": (0, 80),
            "power_consumption": (30, 150),
            "flow_rate": (5, 30)
        },
        "warehouse": {
            "temperature": (15.0, 25.0),
            "pressure": (1000, 1010),
            "humidity": (40, 70),
            "vibration": (0, 50),
            "power_consumption": (20, 100),
            "flow_rate": (2, 15)
        }
    }
    
    # Get the appropriate ranges for the location
    ranges = sensor_ranges.get(location, sensor_ranges["main_facility"])
    
    # Generate realistic sensor data
    current_time = datetime.now(timezone.utc).isoformat()
    
    all_sensor_data = {
        "temperature": {
            "value": round(random.uniform(*ranges["temperature"]), 1),
            "unit": "°C",
            "status": "normal" if random.random() > 0.1 else "warning",
            "last_calibrated": "2024-01-15T10:30:00Z"
        },
        "pressure": {
            "value": round(random.uniform(*ranges["pressure"]), 1),
            "unit": "hPa",
            "status": "normal" if random.random() > 0.05 else "alert",
            "last_calibrated": "2024-01-10T14:20:00Z"
        },
        "humidity": {
            "value": round(random.uniform(*ranges["humidity"]), 1),
            "unit": "%",
            "status": "normal",
            "last_calibrated": "2024-01-12T09:15:00Z"
        },
        "vibration": {
            "value": round(random.uniform(*ranges["vibration"]), 2),
            "unit": "Hz",
            "status": "normal" if random.random() > 0.15 else "warning",
            "last_calibrated": "2024-01-08T16:45:00Z"
        },
        "power_consumption": {
            "value": round(random.uniform(*ranges["power_consumption"]), 2),
            "unit": "kW",
            "status": "normal",
            "last_calibrated": "2024-01-20T11:00:00Z"
        },
        "flow_rate": {
            "value": round(random.uniform(*ranges["flow_rate"]), 2),
            "unit": "L/min",
            "status": "normal" if random.random() > 0.08 else "warning",
            "last_calibrated": "2024-01-18T13:30:00Z"
        }
    }
    
    # Prepare response data
    response_data = {
        "location": location,
        "timestamp": current_time,
        "sensors": {}
    }
    
    if sensor_type.lower() == "all":
        response_data["sensors"] = all_sensor_data
    elif sensor_type.lower() in all_sensor_data:
        response_data["sensors"] = {sensor_type.lower(): all_sensor_data[sensor_type.lower()]}
    else:
        # Return error for invalid sensor type
        available_sensors = list(all_sensor_data.keys())
        error_response = {
            "error": f"Invalid sensor type: {sensor_type}",
            "available_sensors": available_sensors,
            "location": location,
            "timestamp": current_time
        }
        return json.dumps(error_response, indent=2)
    
    return json.dumps(response_data, indent=2)


def _get_system_status(system_component: str = "all") -> str:
    """Direct function to get system status without tool wrapper."""
    logger.info(f"Direct API call for component: {system_component}")
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    system_components = {
        "motors": {
            "motor_1": {"status": "running", "rpm": random.randint(1800, 3600), "temperature": round(random.uniform(40, 80), 1)},
            "motor_2": {"status": "running", "rpm": random.randint(1500, 3200), "temperature": round(random.uniform(35, 75), 1)},
            "motor_3": {"status": "idle", "rpm": 0, "temperature": round(random.uniform(20, 30), 1)}
        },
        "pumps": {
            "pump_a": {"status": "active", "flow_rate": round(random.uniform(15, 45), 2), "pressure": round(random.uniform(2.5, 4.0), 1)},
            "pump_b": {"status": "active", "flow_rate": round(random.uniform(20, 50), 2), "pressure": round(random.uniform(3.0, 4.5), 1)},
            "pump_c": {"status": "maintenance", "flow_rate": 0, "pressure": 0}
        },
        "controllers": {
            "plc_1": {"status": "online", "cpu_usage": random.randint(15, 85), "memory_usage": random.randint(30, 70)},
            "plc_2": {"status": "online", "cpu_usage": random.randint(20, 90), "memory_usage": random.randint(25, 65)},
            "hmi_panel": {"status": "online", "response_time": round(random.uniform(50, 200), 1)}
        },
        "network": {
            "main_switch": {"status": "online", "port_utilization": random.randint(40, 80)},
            "wireless_ap": {"status": "online", "connected_devices": random.randint(5, 15)},
            "firewall": {"status": "active", "threats_blocked": random.randint(0, 5)}
        }
    }
    
    response_data = {
        "timestamp": current_time,
        "components": {}
    }
    
    if system_component.lower() == "all":
        response_data["components"] = system_components
    elif system_component.lower() in system_components:
        response_data["components"] = {system_component.lower(): system_components[system_component.lower()]}
    else:
        available_components = list(system_components.keys())
        error_response = {
            "error": f"Invalid system component: {system_component}",
            "available_components": available_components,
            "timestamp": current_time
        }
        return json.dumps(error_response, indent=2)
    
    return json.dumps(response_data, indent=2)
