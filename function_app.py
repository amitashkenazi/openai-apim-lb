import logging
import azure.functions as func
from simple_priority_handler import set_priority
import os
app = func.FunctionApp()

@app.schedule(schedule="0 1 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def priority_job(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')
    logging.info('Python timer trigger function executed.')
    if os.environ.get("API_SUBSCRIPTION_KEY") is None:
        logging.error("API_SUBSCRIPTION_KEY is not set")
    else :
        logging.info("API_SUBSCRIPTION_KEY is set")
        if os.environ.get("API_URL") is None:
            logging.error("API_URL is not set")
        else :
            logging.info("API_URL is set")
            set_priority(priority_step_ms=500, loop_interval=10, loops_count=3)

