from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import pymysql
import uvicorn
import time
import json
import sys
import os

load_dotenv()

# Logging is configured before anything else so every module and uvicorn itself
# write through the same handlers and the terminal stays readable.
from logger import setup_logging, get_logger, banner

setup_logging()

log = get_logger("api")

from validation_offline import validate_offline_data
from validation_realtime import validate_realtime_data

from save_excel import save_log_to_csv

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# =====================================================
# STARTUP / SHUTDOWN
# =====================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once on startup, and again after the yield on shutdown."""

    banner([
        "DataQC API",
        "",
        f"Listening   : http://{HOST}:{PORT}",
        f"Swagger UI  : http://{HOST}:{PORT}/docs",
        f"Log level   : {os.getenv('LOG_LEVEL', 'INFO').upper()}",
        "Logs        : terminal only, not written to disk",
        f"Working dir : {os.getcwd()}",
    ])

    if not os.getenv("DB_USERNAME") or not os.getenv("DB_PASSWORD"):
        log.warning(
            "DB_USERNAME / DB_PASSWORD not set - /DataQC_offline will fail. "
            "Copy .env.example to .env and fill it in."
        )
    else:
        log.info(
            "Database credentials loaded (user=%s, port=%s)",
            os.getenv("DB_USERNAME"),
            os.getenv("DB_PORT"),
        )

    log.info("Startup complete, waiting for requests")

    yield

    log.info("DataQC API stopped")


app = FastAPI(title="DataQC API", lifespan=lifespan)


# =====================================================
# REQUEST LOGGING
# =====================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One line when a request arrives, one when it leaves, with timing."""

    started = time.perf_counter()

    log.info("--> %s %s", request.method, request.url.path)

    try:
        response = await call_next(request)

    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        # One readable line here; uvicorn prints the full traceback once,
        # so logging it again would double every stack trace.
        exc = sys.exc_info()[1]
        log.error(
            "<-- %s %s  CRASHED after %.1fms  (%s: %s)",
            request.method,
            request.url.path,
            elapsed,
            type(exc).__name__,
            exc,
        )
        raise

    elapsed = (time.perf_counter() - started) * 1000

    emit = log.info if response.status_code < 400 else log.warning
    emit(
        "<-- %s %s  %s  %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )

    return response


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
        log.info(
            "Connecting to MySQL %s:%s  database=%s  table=%s",
            request.ip,
            os.getenv("DB_PORT"),
            request.database_name,
            request.table_name,
        )

        conn = pymysql.connect(
            host=request.ip,
            user=os.getenv("DB_USERNAME"),
            password=os.getenv("DB_PASSWORD"),
            port=int(os.getenv("DB_PORT")),
            database=request.database_name,
            charset="utf8"
        )

        log.info("Connected to MySQL")

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
            log.info("Time filter  : %s -> %s", request.start_date, request.end_date)

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
            log.info("Depth filter : %s -> %s", request.start_depth, request.end_depth)

        if not conditions:
            log.warning(
                "No time or depth filter given - reading the entire %s table",
                request.table_name,
            )

        query = f"SELECT * FROM `{request.table_name}`"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY TIME"

        log.debug("Query: %s  params=%s", query, params)

        fetch_started = time.perf_counter()

        cursor.execute(query, tuple(params))

        data = cursor.fetchall()

        log.info(
            "Fetched %s row(s) in %.0fms",
            len(data),
            (time.perf_counter() - fetch_started) * 1000,
        )

        cursor.close()
        conn.close()

        log.debug("MySQL connection closed")

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

        log.info("Raw rows written to mysql_data.json")

        log.info("Running offline validation on %s row(s)...", len(data))

        notification_report = validate_offline_data(data)

        log.info("Validation finished")

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
        log.exception("Offline QC failed: %s", e)

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

    log.info(
        "Reading received: activity=%s depth=%s SPP=%s TotalSPM=%s ROP=%s",
        data.get("Activity"),
        data.get("depth"),
        data.get("SPP"),
        data.get("TotalSPM"),
        data.get("ROP"),
    )

    alerts, spp_pct, totalspm_pct, rop_pct = validate_realtime_data(data)

    if alerts:
        log.warning("%s alert(s) raised:", len(alerts))

        for alert in alerts:
            log.warning("   %s", alert)
    else:
        log.info("Reading passed every check")

    log.debug(
        "Percent change - SPP=%s TotalSPM=%s ROP=%s", spp_pct, totalspm_pct, rop_pct
    )

    response = {"status": "success", "alerts": alerts}

    save_log_to_csv(
        request_data=data,
        response_data=response,
        spp_percentage=spp_pct,
        totalspm_percentage=totalspm_pct,
        rop_percentage=rop_pct,
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
        host=HOST,
        port=PORT,
        log_config=None,   # keep our own formatting, do not let uvicorn reset it
    )
