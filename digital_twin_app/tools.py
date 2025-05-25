"""
Tools for the Digital Twin Agent
"""
import random
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
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
