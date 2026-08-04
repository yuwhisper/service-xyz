import os

ACCESS_KEY_ID = os.getenv("YINGDAO_ACCESS_KEY_ID", "")
ACCESS_KEY_SECRET = os.getenv("YINGDAO_ACCESS_KEY_SECRET", "")
TOKEN_URL = os.getenv(
    "YINGDAO_TOKEN_URL",
    "https://api.yingdao.com/oapi/token/v2/token/create",
)
JOB_START_URL = os.getenv(
    "YINGDAO_JOB_START_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/job/start",
)
JOB_QUERY_URL = os.getenv(
    "YINGDAO_JOB_QUERY_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/job/query",
)
CLIENT_LIST_URL = os.getenv(
    "YINGDAO_CLIENT_LIST_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/client/list",
)
ROBOT_QUERY_URL = os.getenv(
    "YINGDAO_ROBOT_QUERY_URL",
    "https://api.yingdao.com/oapi/robot/v2/query",
)
SCHEDULE_LIST_URL = os.getenv(
    "YINGDAO_SCHEDULE_LIST_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/schedule/list",
)
SCHEDULE_DETAIL_URL = os.getenv(
    "YINGDAO_SCHEDULE_DETAIL_URL",
    "https://api.yingdao.com/oapi/dispatch/v2/schedule/detail",
)
