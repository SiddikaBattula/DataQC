
from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json
import os

from parameter_validate import (
    validate_ranges,
    validate_activity_conditions,
    validate_ta_tg,
    validate_spp_change,
    validate_totalspm_change,
    validate_rop_change
)
from save_excel import save_log_to_csv
import uvicorn

app = FastAPI()


class DrillingInput(BaseModel):
    Activity: str
    depth: float
    ROP: float
    Hookload: float
    WOB: float
    TotalRPM: float
    TotalSPM: float
    SPP: float
    TG: float
    TA: float
    MW_IN: float
    MW_Out: float
    Temp_In: float
    Temp_Out: float
    H2S: float
    LEL: float
    Co2: float




@app.post("/DataQC_real")
async def DataQC_real(payload: DrillingInput):

    data = payload.model_dump()

    activity_alerts = validate_activity_conditions(data)
    range_alerts = validate_ranges(data)
    ta_tg_alert = validate_ta_tg(data)
    spp_alerts = []
    spp_percentage = 0.0
    if data.get("SPP", 0) > 0:
        spp_alerts, spp_percentage = validate_spp_change(data)
    
    totalspm_alerts, totalspm_percentage = validate_totalspm_change(data)
    rop_alert,rop_percentage=validate_rop_change(data)

    response = {
        "status": "success",
        "alert1": range_alerts,
        "alert2": activity_alerts,
        "alert3": ta_tg_alert,
        "alert4": spp_alerts,
        "alert5": totalspm_alerts,
        "alert6": rop_alert
    }
    # Save request + response locally
    save_log_to_csv(
        request_data=data,
        response_data=response,
        spp_percentage=spp_percentage,
        totalspm_percentage=totalspm_percentage,
        rop_percentage=rop_percentage
    )

    return response


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
