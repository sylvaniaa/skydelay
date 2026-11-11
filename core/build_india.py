import os

import pandas as pd

SRC = os.path.expanduser("~/Documents/FYP/dataset/dgca_flights_emissions_weighted.csv")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(SRC)
m = (df.groupby(["Airline", "Year", "Month"])
       .agg(n_days=("Date", "nunique"),
            departures=("Departures", "first"),
            days_in_month=("days_in_month", "first"),
            otp_pct=("OTP_pct", "mean"),
            p_delay=("P_Delay", "mean"),
            exp_delay_min=("Expected_Delay_Minutes", "mean"),
            co2_daily_mean=("total_extra_co2_kg", "mean"))
       .reset_index())

# monthly CO2 = average daily CO2 x days in month (some months have only a few days of data)
m["co2_tonnes"] = m.co2_daily_mean * m.days_in_month / 1000
m = m.drop(columns=["co2_daily_mean"])
m.to_csv(os.path.join(OUT, "india_monthly.csv"), index=False)

print("rows:", len(m), "| airlines:", m.Airline.nunique())
print(m[(m.Airline == "Air India") & (m.Year == 2024) & (m.Month == 1)].T)
print("months per year:")
print(m.groupby("Year").Month.nunique())
print("partial months (<20 days of data):", int((m.n_days < 20).sum()), "of", len(m))
print(m.groupby("Airline")[["otp_pct", "exp_delay_min", "co2_tonnes"]].mean().round(1))