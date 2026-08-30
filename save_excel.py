from datetime import datetime
import pandas as pd
import os


def save_log_to_csv(
    request_data,
    response_data,
    spp_percentage,
    totalspm_percentage,
    rop_percentage
):

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    today = datetime.now().strftime("%d-%m-%y")
    file_name = os.path.join(
        output_dir,
        f"{today}_data.csv"
    )

    row = {
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "Activity": request_data.get("Activity"),
        "Depth": request_data.get("depth"),
        "ROP": request_data.get("ROP"),
        "Hookload": request_data.get("Hookload"),
        "WOB": request_data.get("WOB"),
        "TotalRPM": request_data.get("TotalRPM"),
        "TotalSPM": request_data.get("TotalSPM"),
        "SPP": request_data.get("SPP"),

        "SPP_%_Change": spp_percentage,
        "TotalSPM_%_Change": totalspm_percentage,
        "ROP_%_Change": rop_percentage,

        "TG": request_data.get("TG"),
        "TA": request_data.get("TA"),
        "MW_IN": request_data.get("MW_IN"),
        "MW_Out": request_data.get("MW_Out"),
        "Temp_In": request_data.get("Temp_In"),
        "Temp_Out": request_data.get("Temp_Out"),
        "H2S": request_data.get("H2S"),
        "LEL": request_data.get("LEL"),
        "Co2": request_data.get("Co2"),

        # main.py sends {"status": ..., "alerts": [...]} - a single list, not
        # the six alert1..alert6 keys this used to read.
        "Alert_Count": len(response_data.get("alerts", [])),
        "Alerts": " | ".join(response_data.get("alerts", []))
    }

    df_new = pd.DataFrame([row])

    if os.path.exists(file_name):
        df_existing = pd.read_csv(file_name)
        df_final = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_final = df_new

    df_final.to_csv(file_name, index=False)