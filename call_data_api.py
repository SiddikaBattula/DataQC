from fastapi import param_functions
from fastapi import param_functions
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from parameter_validate import generate_notification_report
import pymysql
import uvicorn
import json
import os

load_dotenv()

app = FastAPI()



class DataRequest(BaseModel):
    ip: str
    database_name: str
    table_name: str

    start_date: Optional[str] = None
    end_date: Optional[str] = None

    start_depth: Optional[float] = None
    end_depth: Optional[float] = None



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

        # Date filter
        if request.start_date is not None and request.end_date is not None:
            conditions.append("TIME BETWEEN %s AND %s")
            params.extend([
                request.start_date,
                request.end_date
            ])

        # Depth filter
        if request.start_depth is not None and request.end_depth is not None:
            conditions.append("DMEA BETWEEN %s AND %s")
            params.extend([
                request.start_depth,
                request.end_depth
            ])

        query = f"SELECT * FROM `{request.table_name}`"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        # Order by TIME if date filter is used,
        # otherwise order by DEPTH
        
        query += " ORDER BY TIME"
       

        cursor.execute(query, tuple(params))

        data = cursor.fetchall()

        cursor.close()
        conn.close()

        with open("mysql_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, default=str)

        notification_report = generate_notification_report(data)
        print("QUERY:", query)
        print("PARAMS:", params)
        return{
            "status": "success",
            "filters": {
                "start_date": request.start_date,
                "end_date": request.end_date,
                "start_depth": request.start_depth,
                "end_depth": request.end_depth
            },
            "alerts": notification_report
        }


    except Exception as e:
        print("error:",e)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


if __name__ == "__main__":
    uvicorn.run(
        "call_data_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )