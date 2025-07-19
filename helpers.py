import time

def log(text):
    log_time = time.strftime('%H:%M:%S', time.localtime(time.time()))
    print(f"[{log_time}] {text}")


def convert(variable, variable_type):
    if variable_type is float:
        try:
            return float(variable)
        except ValueError:
            return 0.0
        
    if variable_type is int:
        try:
            return int(variable)
        except ValueError:
            return 0
        
    if variable_type is str:
        try:
            return str(variable)
        except ValueError:
            return ""
    
    raise TypeError("Type Not Supported By Helper Function")
