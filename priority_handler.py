import os
import logging
import azure.functions as func
from azure.cosmos import CosmosClient
import json
import requests
import datetime
import time

# Environment Variables
cosmos_db_url = os.environ.get('COSMOS_DB_URL')
cosmos_db_key = os.environ.get('COSMOS_DB_KEY')
api_subscription_key = os.environ.get('API_SUBSCRIPTION_KEY')
database_name = os.environ.get('DATABASE_NAME')
container_name = os.environ.get('CONTAINER_NAME')

# Function for Changing Priority
def change_priority(priorities):
    print("change priority")
    print(priorities)
    url = "https://apim-openai-lb.azure-api.net/set_be_priority"
    payload = json.dumps(priorities)
    headers = {
        'Ocp-Apim-Subscription-Key': api_subscription_key,
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.text)

# Function for Parsing Datetime Strings
def parse_datetime(dt_str):
    datetime_str = dt_str.rstrip('Z')
    if '.' in datetime_str:
        main_part, fractional_part = datetime_str.split('.')
        fractional_part += "0000"
        fractional_part = fractional_part[:6]  # Keep only the first six digits
        datetime_str = main_part + '.' + fractional_part
    return datetime.datetime.fromisoformat(datetime_str)


def set_priorities():

    logging.info('Python timer trigger function executed.')
    # Initialize the Cosmos client
    client = CosmosClient(cosmos_db_url, credential=cosmos_db_key)

    # Get the container client
    container_client = client.get_database_client(database_name).get_container_client(container_name)

    # Get the current time minus one minute
    ts_th = int(time.time()) - 60

    # Query to get documents uploaded in the last minute
    query = f"SELECT * FROM c WHERE c._ts > {ts_th}"
    performance = {}

    # Execute the query
    for idx, item in enumerate(container_client.query_items(
            query=query,
            enable_cross_partition_query=True)):
        print(f"---item {idx}---")
        start_time_str = item.get("StartTime")
        end_time_str = item.get("EndTime")
        CompletionTokens = int(item.get("CompletionTokens"))
        backendUrl = item.get("backendUrl")
        if start_time_str and end_time_str:
            start_time = parse_datetime(start_time_str)
            end_time = parse_datetime(end_time_str)

            response_time_ms = (end_time - start_time).total_seconds() * 1000
            token_response_time_ratio = response_time_ms / CompletionTokens
            if backendUrl not in performance:
                performance[backendUrl] = []
            performance[backendUrl].append(token_response_time_ratio)
    
    # Calculate average performance
    performance_avg = {k: sum(v)/len(v) for k, v in performance.items() if v}
    sorted_names = sorted(performance_avg, key=performance_avg.get)
    change_priority_dict = {n[:-7]: idx for idx, n in enumerate(sorted_names)}

    change_priority(change_priority_dict)

# Add any additional code or functions here if necessary
