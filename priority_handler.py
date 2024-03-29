import os
import logging
from azure.cosmos import CosmosClient
import json
import requests
import datetime
import time

PLOT_GRAPH = True
pushback_interval_seconds = 60


cosmos_db_url = os.environ.get('COSMOS_DB_URL', 'https://openai-logger.documents.azure.com:443/')
cosmos_db_key = os.environ.get('COSMOS_DB_KEY')
api_subscription_key = os.environ.get('API_SUBSCRIPTION_KEY')
database_name = os.environ.get('COSMOS_DB_DATABASE_NAME', 'openai-logger')
container_name = os.environ.get('COSMOS_DB_CONTAINER_NAME', 'openai-logger-events')
api_url = os.environ.get('API_URL', 'https://apim-openai-lb.azure-api.net/set_be_priority')

# Function for Changing Priority
def change_priority(url, priorities):
    payload = json.dumps(priorities)
    headers = {
        'Ocp-Apim-Subscription-Key': api_subscription_key,
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    logging.info(response.text)

# Function for Parsing Datetime Strings
def parse_datetime(dt_str):
    datetime_str = dt_str.rstrip('Z')
    if '.' in datetime_str:
        main_part, fractional_part = datetime_str.split('.')
        fractional_part += "0000"
        fractional_part = fractional_part[:6]  # Keep only the first six digits
        datetime_str = main_part + '.' + fractional_part
    return datetime.datetime.fromisoformat(datetime_str)

def get_backends(client):
    container_client = client.get_database_client(database_name).get_container_client("backends")
    backends = []
    for item in container_client.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True):
        if item.get('backends'):
            backends+=item['backends']
    return backends

def get_docs_from_cosmos(client, query):
    docs = []
    for item in client.query_items(
            query=query,
            enable_cross_partition_query=True):
        docs.append(item)
    return docs

def set_priorities(window_size_seconds=60, priority_step=50):
    calls_number = {}
    response_parameter = {}
    change_priority_dict = {}

    # Initialize the Cosmos client
    client = CosmosClient(cosmos_db_url, credential=cosmos_db_key)
    backends = get_backends(client)
    # Get the container client
    container_client = client.get_database_client(database_name).get_container_client(container_name)
    
    

    # Get the current time minus one minute
    ts_th = int(time.time()) - window_size_seconds

    # Query to get documents uploaded in the last minute
    query = f"SELECT * FROM c WHERE c._ts > {ts_th}"
    performance = {}
    items = get_docs_from_cosmos(container_client, query)
    # Execute the query
    for idx, item in enumerate(items):
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

    for k, v in performance_avg.items():
        if k not in calls_number:
            calls_number[k] = []
        if k not in response_parameter:
            response_parameter[k] = []
        calls_number[k].append(len(performance[k]))
        response_parameter[k].append(v)
    change_priority_dict = {}
    sorted_names = sorted(performance_avg, key=performance_avg.get)
    # set priority based on performance. if the next performance value is bigger than previous value + priority_step, then set the priority to previous value + 1
    final_priority = 0
    for idx, n in enumerate(sorted_names):
        if idx == 0:
            change_priority_dict[n[:-7]] = 0
        else:
            if performance_avg[n] > performance_avg[sorted_names[idx-1]] + priority_step:
                change_priority_dict[n[:-7]] = change_priority_dict[sorted_names[idx-1][:-7]] + 1
            else:
                change_priority_dict[n[:-7]] = change_priority_dict[sorted_names[idx-1][:-7]] 
        final_priority = idx

    # check which backend is missing in the priority list and count the last time it was called from cosmos db
    for backend in backends:
        logging.info(f"Checking backend {backend}")
    # Make sure 'backend' is a valid string for use in the query
        if not any(backend.startswith(prefix) for prefix in change_priority_dict):
            change_priority_dict[backend+"/openai"] = final_priority + 1
            calls_number[backend+"/openai"] = [0]
            response_parameter[backend+"/openai"] = [0]
            try:
                query = f"SELECT TOP 1 * FROM c WHERE STARTSWITH(c.backendUrl, '{backend}') ORDER BY c._ts DESC"
                items = list(container_client.query_items(
                        query=query,
                        enable_cross_partition_query=True))

                # Check if any items were returned
                if items:
                    item = items[0]
                    last_time = item['_ts']
                    logging.info(f"Backend {backend} was not called in the last {int(time.time()) - last_time} seconds. Setting priority to 0")
                    if int(time.time()) - last_time > pushback_interval_seconds:
                        logging.info(f"Setting priority to 0")
                        change_priority_dict[backend] = 0
                else:
                    logging.info(f"No records found for backend={backend}")
            except azure.cosmos.exceptions.CosmosHttpResponseError as e:
                logging.info(f"Error querying Cosmos DB: {e}")


    change_priority(api_url, change_priority_dict)
    return response_parameter, calls_number, change_priority_dict

# Add any additional code or functions here if necessary


if __name__ == "__main__":

    # configure  the logging debugger
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    # Set up a higher logging level specifically for Azure Cosmos DB to silence its logs
    cosmos_logger = logging.getLogger('azure.cosmos')
    cosmos_logger.setLevel(logging.WARNING)


    import matplotlib.pyplot as plt
    calls_number_plot = {}
    response_parameter_plot = {}
    timestamps = []
    change_priority_dict_plot = {}


    def update_plot(response_parameter, calls_number, change_priority_dict):
        # Clear current plots
        plt.clf()

        # Plot new data
        for backend_url in response_parameter:
            plt.plot(response_parameter[backend_url], label=f"{backend_url} - Response Time {change_priority_dict[backend_url[:-7]][-1]}")
        # Get the legend info for first plot
        handles1, labels1 = plt.gca().get_legend_handles_labels()

        ax2 = plt.twinx()  # Create a second y-axis
        for backend_url in calls_number:
            ax2.plot(calls_number[backend_url], '--', label=f"{backend_url} - Calls Number {change_priority_dict[backend_url[:-7]][-1]}")
        # Get the legend info for second plot
        handles2, labels2 = ax2.get_legend_handles_labels()

        # plot the priorites in a separate scale in the same plot
        priorities = []
        for backend_url in response_parameter:
            if backend_url[:-7] in change_priority_dict:
                priorities.append(change_priority_dict[backend_url[:-7]])
            else:
                priorities.append(-1)
        
        plt.legend(handles1 + handles2, labels1 + labels2)
    
        plt.xlabel('Time')
        plt.ylabel('Value')
        ax2.set_ylabel('Number of Calls')  # Set label for the second y-axis
        plt.title('Backend Performance Over Time')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
        plt.pause(0.001)
    # load local.settings.json and set environment variables
    with open("local.settings.json") as f:
        settings = json.load(f)
        for k, v in settings["Values"].items():
            os.environ[k] = v
    cosmos_db_url = os.environ.get('COSMOS_DB_URL', 'https://openai-logger.documents.azure.com:443/')
    cosmos_db_key = os.environ.get('COSMOS_DB_KEY')
    api_subscription_key = os.environ.get('API_SUBSCRIPTION_KEY')
    database_name = os.environ.get('COSMOS_DB_DATABASE_NAME', 'openai-logger')
    container_name = os.environ.get('COSMOS_DB_CONTAINER_NAME', 'openai-logger-events')
    api_url = os.environ.get('API_URL', 'https://apim-openai-lb.azure-api.net/set_be_priority')
    
    plt.figure()
    plt.ion()
    
    while True:
        response_parameter, calls_number, change_priority_dict = set_priorities(window_size_seconds=60, priority_step=50)
        for k in calls_number.keys():
            if k not in calls_number_plot:
                calls_number_plot[k] = []
            calls_number_plot[k] += calls_number[k]
        for k in response_parameter.keys():
            if k not in response_parameter_plot:
                response_parameter_plot[k] = []
            response_parameter_plot[k] += response_parameter[k]
        for k in change_priority_dict.keys():
            if k not in change_priority_dict_plot:
                change_priority_dict_plot[k] = []
            change_priority_dict_plot[k].append(change_priority_dict[k])
        
            
        update_plot(response_parameter_plot, calls_number_plot, change_priority_dict_plot)
        time.sleep(10)  # Adjust the sleep time as needed
