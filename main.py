from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import pymysql
import uvicorn
import json
import os

from parameter_validate import (
    generate_notification_report,
    validate_ranges,
    validate_activity_conditions,
    validate_ta_tg,
    validate_spp_change,
    validate_totalspm_change,
    validate_rop_change
)

from save_excel import save_log_to_csv

load_dotenv()

app = FastAPI(title="DataQC API")


# =====================================================
# OFFLINE REQUEST MODEL
# =====================================================

class DataRequest(BaseModel):
    ip: str
    database_name: str
    table_name: str

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    start_depth: Optional[float] = None
    end_depth: Optional[float] = None


# =====================================================
# REALTIME REQUEST MODEL
# =====================================================

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


# =====================================================
# OFFLINE DATA QC
# =====================================================

@app.post("/DataQC_offline")
def DataQC_offline(request: DataRequest):

    try:
        conn = pymysql.connect(
            host=request.ip,
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT")),
            database=request.database_name,
            charset="utf8"
        )

        cursor = conn.cursor(pymysql.cursors.DictCursor)

        conditions = []
        params = []

        # TIME FILTER
        if request.start_date and request.end_date:
            conditions.append("TIME BETWEEN %s AND %s")
            params.extend([
                request.start_date,
                request.end_date
            ])

        # DEPTH FILTER
        if (
            request.start_depth is not None
            and request.end_depth is not None
        ):
            conditions.append("DMEA BETWEEN %s AND %s")
            params.extend([
                request.start_depth,
                request.end_depth
            ])

        query = f"SELECT * FROM `{request.table_name}`"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY TIME"

        cursor.execute(query, tuple(params))

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        with open(
            "mysql_data.json",
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                data,
                f,
                indent=4,
                default=str
            )

        notification_report = generate_notification_report(data)

        return {
            "status": "success",
            "rows": len(data),
            "filters": {
                "start_date": request.start_date,
                "end_date": request.end_date,
                "start_depth": request.start_depth,
                "end_depth": request.end_depth
            },
            "alerts": notification_report
        }

    except Exception as e:
        print("error:", e)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =====================================================
# REALTIME DATA QC
# =====================================================

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

    totalspm_alerts, totalspm_percentage = (
        validate_totalspm_change(data)
    )

    rop_alert, rop_percentage = (
        validate_rop_change(data)
    )

    response = {
        "status": "success",
        "alert1": range_alerts,
        "alert2": activity_alerts,
        "alert3": ta_tg_alert,
        "alert4": spp_alerts,
        "alert5": totalspm_alerts,
        "alert6": rop_alert
    }

    save_log_to_csv(
        request_data=data,
        response_data=response,
        spp_percentage=spp_percentage,
        totalspm_percentage=totalspm_percentage,
        rop_percentage=rop_percentage
    )

    return response


# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/")
def home():
    return {
        "message": "DataQC API Running"
    }


# =====================================================
# START SERVER
# =====================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000
    )