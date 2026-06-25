import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from app.config import MIN_LAT, MAX_LAT, MIN_LON, MAX_LON, NUM_AIS_RECORDS

VESSEL_TYPE_MAP = {
    30: "fishing", 31: "towing", 32: "towing large", 33: "dredging", 34: "diving",
    35: "military", 36: "sailing", 37: "pleasure", 40: "high speed craft",
    50: "pilot", 51: "search and rescue", 52: "tug", 53: "port tender",
    54: "anti-pollution", 55: "law enforcement", 58: "medical transport",
    60: "passenger", 70: "cargo", 71: "container", 79: "ro-ro cargo",
    80: "tanker", 89: "other tanker", 90: "other"
}

def generate_ship_type():
    r = np.random.random()
    if r < 0.4:
        return np.random.choice([70,71,72,79])
    elif r < 0.65:
        return np.random.choice([80,81,82,89])
    elif r < 0.8:
        return np.random.choice([60,61,62,69])
    elif r < 0.9:
        return 52
    else:
        return np.random.choice([30,31,36,37,50,51,55,90])

def generate_ais_record(timestamp, idx):
    lat = np.random.uniform(MIN_LAT, MAX_LAT)
    lon = np.random.uniform(MIN_LON, MAX_LON)
    if lon > 180:
        lon = lon - 360
    sog = min(30, np.random.exponential(scale=5))
    cog = np.random.uniform(0, 360)
    vessel_type_code = generate_ship_type()
    mmsi = 300000000 + np.random.randint(0, 99999999)
    length = np.random.choice([20,30,50,100,200,300], p=[0.3,0.25,0.2,0.15,0.07,0.03])
    width = np.random.choice([5,8,10,15,20,30,40], p=[0.2,0.2,0.2,0.15,0.1,0.1,0.05])
    draft = np.random.uniform(2, 12) if length > 100 else np.random.uniform(1, 5)
    return {
        "mmsi": mmsi,
        "base_date_time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "longitude": lon,
        "latitude": lat,
        "sog": sog,
        "cog": cog,
        "heading": int(cog) if np.random.random() > 0.2 else None,
        "vessel_name": f"VESSEL_{idx}",
        "imo": f"IMO{np.random.randint(1000000, 9999999)}",
        "call_sign": "".join(np.random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"), 7)),
        "vessel_type": vessel_type_code,
        "status": np.random.choice([0,1,5,8,15]),
        "length": length,
        "width": width,
        "draft": draft,
        "cargo": np.random.choice([0,1,2,3,4,5,6,7,8,9]),
        "transceiver": "A" if np.random.random() > 0.3 else "B"
    }

def generate_ais_dataset(num_records=NUM_AIS_RECORDS):
    start_date = datetime.now() - timedelta(days=30)
    records = []
    for i in range(num_records):
        timestamp = start_date + timedelta(seconds=np.random.randint(0, 30*24*3600))
        records.append(generate_ais_record(timestamp, i))
        if (i+1) % 50000 == 0:
            print(f"Generated {i+1} records")
    df = pd.DataFrame(records)
    df['base_date_time'] = pd.to_datetime(df['base_date_time'])
    return df

if __name__ == "__main__":
    df = generate_ais_dataset()
    df.to_parquet("data/synthetic_ais.parquet", index=False)
    print("Saved to data/synthetic_ais.parquet")