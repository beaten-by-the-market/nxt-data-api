"""nxt-data-api — 넥스트레이드(nextrade.co.kr) 거래현황 호출 클라이언트.

빠른 시작
---------
>>> from nxt_data_api import fetch
>>> df = fetch("regular_market", date="20260812")   # 거래현황 > 정규시장
>>> df = fetch("closing_price", date="20260812")    # 거래현황 > 종가매매
>>> df = fetch("regular_market")                    # 날짜 생략 = 당일 실시간 스냅샷

기간 조회는 하루씩 돌며 이어 붙입니다.

>>> from nxt_data_api import fetch_range
>>> df = fetch_range("regular_market", "20260801", "20260812")

로그인이 필요 없습니다 (KRX 정보데이터시스템과 달리 OTP·세션 인증이 없습니다).
"""

from .client import (
    endpoint_info,
    fetch,
    fetch_range,
    list_endpoints,
    register_post_processor,
)
from .exceptions import NXTError, NXTFetchError, UnknownEndpointError

__all__ = [
    "fetch",
    "fetch_range",
    "list_endpoints",
    "endpoint_info",
    "register_post_processor",
    "NXTError",
    "NXTFetchError",
    "UnknownEndpointError",
]

__version__ = "0.1.0"
