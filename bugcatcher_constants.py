
from enum import Enum

class ProxyConfig:
    BASE_URL = "http://localhost:8085"
    SCREENSHOT_ENDPOINT = f"{BASE_URL}/screenshot"
    TAP_ENDPOINT = f"{BASE_URL}/tap"
    TIMEOUT_GENERAL = 10
    TIMEOUT_TAP = 30

class FileConfig:
    DEFAULT_OUTPUT_JSON = "result.json"

class JSONKeys:
    # API Response Keys
    STATUS = 'status'
    DATA = 'data'
    MESSAGE = 'message'
    TOTAL = 'total'
    SUCCESS = 'success'

    # API Status Values
    STATUS_OK = 'ok'

    # Puzzle Data Structure Keys
    GRID_INFO = 'grid_info'
    COLOR_MAP = 'color_map'
    COLOR_MATRIX = 'color_matrix'
    CELLS = 'cells'
    ROWS = 'rows'
    COLS = 'cols'
    ROW = 'row'
    COL = 'col'
    X = 'x'
    Y = 'y'
    W = 'w'
    H = 'h'
