####Parte del calcolo####

import openmeteo_requests
import requests_cache
from retry_requests import retry
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from geopy.geocoders import Nominatim
from tkcalendar import Calendar
import geocoder
from datetime import datetime
import ephem
import numpy as np  # Import numpy


import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)
openmeteo = openmeteo_requests.Client(session = retry_session)

# Make sure all required weather variables are listed here
# The order of variables in hourly or daily is important to assign them correctly below
url = "https://api.open-meteo.com/v1/forecast"
params = {
  #All params are show  at https://open-meteo.com/en/docs in Api Documentation. exaples below 
	#"latitude": 52.52,
	#"longitude": 13.41,
	#"current": "snowfall",
	#"hourly": "temperature_2m",
	#"daily": "snowfall_sum"
}
responses = openmeteo.weather_api(url, params=params) #All parameters that you have request are stored in responses variable

#Exaples of manege responses variable for print inside parameters
# Process first location. Add a for-loop for multiple locations or weather models
#response = responses[0]
#print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
#print(f"Elevation {response.Elevation()} m asl")
#print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
#print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

# Current values. The order of variables needs to be the same as requested.
#current = response.Current()
#current_snowfall = current.Variables(0).Value()

#print(f"Current time {current.Time()}")
#print(f"Current snowfall {current_snowfall}")

# Process hourly data. The order of variables needs to be the same as requested.
#hourly = response.Hourly()
#hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

#hourly_data = {"date": pd.date_range(
	#start = pd.to_datetime(hourly.Time(), unit = "s", utc = True),
	#end = pd.to_datetime(hourly.TimeEnd(), unit = "s", utc = True),
	#freq = pd.Timedelta(seconds = hourly.Interval()),
	#inclusive = "left")}
#hourly_data["temperature_2m"] = hourly_temperature_2m

#hourly_dataframe = pd.DataFrame(data = hourly_data)
#print(hourly_dataframe)

# Process daily data. The order of variables needs to be the same as requested.
#daily = response.Daily()
#daily_snowfall_sum = daily.Variables(0).ValuesAsNumpy()

#daily_data = {"date": pd.date_range(
	#start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
	#end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
	#freq = pd.Timedelta(seconds = daily.Interval()),
	#inclusive = "left")}
#daily_data["snowfall_sum"] = daily_snowfall_sum

#daily_dataframe = pd.DataFrame(data = daily_data)
#print(daily_dataframe)


def get_temperature_range_for_crop(crop):
    # Definisci i valori di temperatura massima e la temperatura minima di accrescimento per ogni coltura
    colture_data = {
        "Pomodoro": (30, 10),  # Esempio di valori per il pomodoro (temperatura massima, temp_min)
        "Grano": (25, 2.5),    # Esempio di valori per il grano
        "Mais": (35, 10)        # Esempio di valori per il mais
        # Aggiungi altri valori per le colture, se necessario
    }
    # Restituisci i valori di temperatura massima e la temperatura minima di accrescimento per la coltura selezionata
    return colture_data.get(crop, (25, 15))  # Valori di default nel caso in cui la coltura non sia definita

def estimate_solar_radiation(latitude, end_date):
    observer = ephem.Observer()
    observer.lat = str(latitude)
    observer.lon = '0'  # Longitudine non è rilevante per la stima della radiazione solare giornaliera
    observer.date = end_date

    # Imposta l'osservatore per il mezzogiorno locale per avere una stima media
    observer.date = ephem.Date(observer.date + 12 * ephem.hour)
    
    # Crea il sole e calcola la sua altezza massima
    sun = ephem.Sun(observer)
    max_altitude = sun.alt

    # Converti l'altezza massima in gradi
    max_altitude_deg = np.degrees(max_altitude)
    
    # Stima della radiazione solare in MJ/m^2/giorno
    solar_radiation = 0.0820 * (max_altitude_deg - 90) * 24 * 3600 / 1e6  # MJ/m^2/giorno

    # Assicurati che la radiazione solare sia sempre positiva
    solar_radiation = max(solar_radiation, 0)

    return solar_radiation

def calculate_et0(latitude, longitude, planting_date, end_date):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m",
        "start": planting_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

    temperature_max = hourly_temperature_2m.max()
    temperature_min = hourly_temperature_2m.min()
    temperature_mean = (temperature_max + temperature_min) / 2

    solar_radiation = estimate_solar_radiation(latitude, end_date)
    et0 = 0.0023 * (temperature_mean + 17.8) * (temperature_max - temperature_min) ** 0.5 * solar_radiation

    return et0, hourly_temperature_2m

def get_location_name(latitude, longitude):
    geolocator = Nominatim(user_agent="calcolatore-et0")
    location = geolocator.reverse((latitude, longitude), exactly_one=True)
    address = location.address
    return address.split(", ")[-3], address.split(", ")[-2]  # Ritorna la provincia e il paese

def get_real_gps_coordinates():
    g = geocoder.ip('me')  # Ottieni le coordinate GPS basate sull'indirizzo IP
    latitude, longitude = g.latlng
    return latitude, longitude

def estimate_phenological_stage(crop, accumulated_gdd):
    # Definisci le fasi fenologiche per le colture
    stages = {
        "Pomodoro": {
            "Germinazione": (0, 100),
            "Emergenza": (100, 200),
            "Fioritura": (200, 300),
            "Raccolta": (300, 400),
        },
        "Grano": {
            "Germinazione": (0, 150),
            "Crescita vegetativa": (150, 300),
            "Infiorescenza": (300, 400),
            "Maturazione": (400, 500),
            "Raccolta": (500, 600),
        },
        "Mais": {
            "Germinazione": (0, 200),
            "Crescita vegetativa": (200, 400),
            "Fioritura": (400, 600),
            "Maturazione": (600, 800),
            "Raccolta": (800, 1000),
        },
    }

    if crop not in stages:
        return "Dati mancanti per la coltura selezionata"
    for stage, (min_gdd, max_gdd) in stages[crop].items():
        if accumulated_gdd >= min_gdd and accumulated_gdd <= max_gdd:
            return stage
    return "Stadio finale"  # Placeholder for the final stage

def calculate_gdd(temperature_max, temperature_min, card_min, card_max):
    temperature_mean = (temperature_max + temperature_min) / 2
    gdd = temperature_mean - card_min
    if gdd > card_max:
        gdd = card_max
    return max(gdd, 0)

def calculate_accumulated_gdd(hourly_temperature_2m, card_min, card_max):
    # Aggrega le temperature orarie in temperature giornaliere
    daily_temperatures = []
    for i in range(0, len(hourly_temperature_2m), 24):
        daily_max = max(hourly_temperature_2m[i:i+24])
        daily_min = min(hourly_temperature_2m[i:i+24])
        daily_temperatures.append((daily_max, daily_min))

    accumulated_gdd = 0
    for temperature_max, temperature_min in daily_temperatures:
        gdd = calculate_gdd(temperature_max, temperature_min, card_min, card_max)
        accumulated_gdd += gdd
    return accumulated_gdd
def calculate_and_show_et0():
    try:
        crop_selection = crop_combo.get()
        planting_date = calendar.selection_get()
        latitude, longitude = get_real_gps_coordinates()
        end_date = datetime.now()
        temperature_max, temperature_min = get_temperature_range_for_crop(crop_selection)
        card_max = temperature_max
        card_min = temperature_min

        et0, hourly_temperature_2m = calculate_et0(latitude, longitude, planting_date, end_date)
        accumulated_gdd = calculate_accumulated_gdd(hourly_temperature_2m, card_min, card_max)

        estimated_stage = estimate_phenological_stage(crop_selection, accumulated_gdd)

        if accumulated_gdd <= 0:
            kc = 0
        elif accumulated_gdd <= 100:
            kc = 0.5
        elif accumulated_gdd <= 200:
            kc = 0.7
        elif accumulated_gdd <= 300:
            kc = 1.2
        else:
            kc = 1.0

        et_stimata = et0 * kc

        provincia, paese = get_location_name(latitude, longitude)
        message = f"""
Posizione: Latitudine: {latitude}, Longitudine: {longitude}, Provincia: {provincia}, Paese: {paese}
Coltura: {crop_selection}
Data di trapianto: {planting_date.strftime('%d/%m/%Y')}
Evapotraspirazione potenziale (ET0): {et0:.2f} mm 
Gradi giorno accumulati: {accumulated_gdd:.1f}
Stadio fenologico stimato: {estimated_stage}
Evapotraspirazione stimata: {et_stimata:.2f} mm 
Coefficiente colturale (Kc): {kc:.2f}
"""
        messagebox.showinfo("Dati stimati", message)
    except Exception as e:
        messagebox.showerror("Errore", f"Si è verificato un errore: {e}")
def main():
    global crop_combo, calendar  # Define crop_combo and calendar as global variables

    # Create the main window
    root = tk.Tk()
    root.title("EtNow")
    root.geometry("500x400")  # Adjust window size as needed
    root.resizable(True, True)  # Allow resizing

    # Set the default font for the entire application
    root.option_add("*Font", "Arial 12")

    # Main frame
    main_frame = ttk.Frame(root, padding=10)
    main_frame.pack(expand=True, fill=tk.BOTH)

    # Add label and combo box for selecting crop with improved styling
    crop_label = ttk.Label(main_frame, text="Seleziona la coltura:", style="CropLabel.TLabel")
    crop_label.grid(row=0, column=0, sticky=tk.W, pady=(10, 0))  # Add padding for spacing

    crop_combo = ttk.Combobox(main_frame, values=["Pomodoro", "Grano", "Mais"], style="CropCombo.TCombobox")
    crop_combo.grid(row=0, column=1, padx=5, pady=5)
    crop_combo.current(0)  # Set default value

    # Style definitions for custom labels and combo boxes
    style = ttk.Style()
    style.configure("CropLabel.TLabel", foreground="#333333", font=("Arial", 12, "bold"))
    style.configure("CropCombo.TCombobox", background="#2c9c91", foreground="#333333", font=("Arial", 12))

    # Add calendar widget for selecting planting date with improved styling
    planting_label = ttk.Label(main_frame, text="Seleziona la data di trapianto:", style="PlantingLabel.TLabel")
    planting_label.grid(row=1, column=0, sticky=tk.W, pady=(10, 0))

    calendar = Calendar(main_frame, selectmode="day", date_pattern="dd/mm/yyyy", style="Calendar.TCalendar")
    calendar.grid(row=1, column=1, padx=5, pady=5)

    # Style definitions for custom planting label and calendar
    style.configure("PlantingLabel.TLabel", foreground="#333333", font=("Arial", 12, "bold"))
    style.configure(
        "Calendar.TCalendar",
        background="#e0e0e0",
        foreground="#333333",
        selectbackground="#3399ff",
        selectforeground="#ffffff",
        font=("Arial", 12),
    )

    # Add button to trigger calculation with improved styling
    calculate_button = ttk.Button(main_frame, text="Ottieni dati", command=calculate_and_show_et0, style="CalculateButton.TButton")
    calculate_button.grid(row=2, column=0, columnspan=2, pady=10)

    # Style definition for calculate button
    style.configure("CalculateButton.TButton", background="#2c9c91", foreground="#2c9c91", font=("Arial", 12, "bold"))

    root.mainloop()

if __name__ == "__main__":
    main()
