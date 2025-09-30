import pandas as pd, random
from datetime import datetime, timedelta, date

months = list(range(1,7)) ; year = 2025 ; rows_per_month = 60
clinics = ["Cartersville","Cedartown","Rockmart","Rome"]
counties = {"Cartersville":"Bartow","Cedartown":"Polk","Rockmart":"Polk","Rome":"Floyd"}
cities   = {"Cartersville":"Cartersville","Cedartown":"Cedartown","Rockmart":"Rockmart","Rome":"Rome"}
zips     = {"Cartersville":["30120","30121"],"Cedartown":["30125"],"Rockmart":["30153"],"Rome":["30161","30165"]}
pract    = {"Cartersville":"Nexa Primary Care - Cartersville","Cedartown":"Nexa Family Health - Cedartown","Rockmart":"Nexa Care - Rockmart","Rome":"Nexa Medical Group - Rome"}
prov     = {
 "Cartersville":[("Dr. Alice Nguyen","1111111111"),("Dr. Eric Patel","2222222222")],
 "Cedartown":[("Dr. Maria Lopez","3333333333"),("Dr. Brian Cohen","4444444444")],
 "Rockmart":[("Dr. Leah Wilson","5555555555"),("Dr. Omar Johnson","6666666666")],
 "Rome":[("Dr. Hannah Kim","7777777777"),("Dr. David Wright","8888888888")]
}
measures = [
 "Hemoglobin A1c Control <8","Kidney Eval: eGFR","Kidney Eval: ACR",
 "High Blood Pressure Control <140/90","Breast Cancer Screening",
 "CAD/IVD Statin Therapy (SPC)","Diabetes Statin Therapy (SUPD)",
 "Well Care Visit 3–21 Years Old"
]
insurers=["Medicare","Medicaid","BCBS","Aetna","Cigna","UnitedHealthcare"]
first=["John","Jane","Michael","Sarah","Robert","Emily","David","Laura","Daniel","Grace","Anthony","Olivia","Isaac","Sophia","Ethan","Ava","Liam","Mia"]
last =["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore"]
streets=["Oak St","Maple Ave","Pine Rd","Cedar Ln","Elm St","River Rd","Hillcrest Dr","Sunset Blvd","Main St","Peachtree St"]

def phone(): return f"770-{random.randint(200,999)}-{random.randint(1000,9999)}"
def addr():  return f"{random.randint(100,9999)} {random.choice(streets)}"
def dob():
  yr = random.randint(1930, 2022); mo = random.randint(1,12); dy = random.randint(1,28)
  return f"{yr:04d}-{mo:02d}-{dy:02d}"
def email(fn,ln,pid): return f"{fn}.{ln}.{pid}@example.com".lower()

rows=[]
for m in months:
  for i in range(1,rows_per_month+1):
    pid = f"{year}{m:02d}{i:04d}"
    clinic = random.choice(clinics)
    city, county = cities[clinic], counties[clinic]
    zipc = random.choice(zips[clinic])
    practice = pract[clinic]
    (prov_name, prov_npi) = random.choice(prov[clinic])
    fn, ln = random.choice(first), random.choice(last)
    d0 = datetime(year, m, random.randint(1,28))
    rows.append({
      "patient_id": pid,
      "first_name": fn, "last_name": ln, "dob": dob(),
      "address": addr(), "city": city, "state":"GA", "zip": zipc, "county": county,
      "phone_mobile": phone(), "phone_home": (phone() if random.random()<0.45 else ""),
      "email": email(fn,ln,pid), "insurance": random.choice(insurers),
      "provider_name": prov_name, "provider_npi": prov_npi,
      "practice": practice, "clinic": clinic,
      "quality_care_gap": random.choice(measures), "measure": random.choice(measures),
      "date": d0.strftime("%Y-%m-%d"),
      "last_visit": (d0 - timedelta(days=random.randint(30,360))).strftime("%Y-%m-%d"),
      "due_date": (d0 + timedelta(days=random.randint(10,120))).strftime("%Y-%m-%d"),
      "compliant": random.choice([True, False, False])
    })

df = pd.DataFrame(rows)
out = "qscore-suite/data/qscore_patients_2025_Jan-Jun_master.csv"
df.to_csv(out, index=False)
print("WROTE:", out, "ROWS:", len(df))
