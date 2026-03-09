from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field
from typing import Union

class ExceptionSuggestionRag(BaseModel):
    order_no: Optional[str] = None
    material_name: Optional[str] = None
    spec: Optional[str] = None
    supplier_name: Optional[str] = None
    customer: Optional[str] = None
    bucket: Optional[str] = None  # 1. 总不良率： 缺陷总和 / 总抽检 不良原因：xxx 2. 最严重缺陷不良率： 最严重缺陷 / 总抽检 （缺陷程度） 不良原因： xxx 注： <2%为轻微；20%内为显著异常；其余为严重