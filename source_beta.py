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

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

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


def calculate_et0(latitude, longitude, planting_date, end_date):
    # Make sure all required weather variables are listed here
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m",
        "start": planting_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d")
    }
    responses = openmeteo.weather_api(url, params=params)

    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()
    hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()

    # Collect temperature data as list of tuples (temperature_max, temperature_min)
    temperature_data = [(hourly_temperature_2m[i], hourly_temperature_2m[i+1]) for i in range(0, len(hourly_temperature_2m), 2)]

    # Calcolo dell'ET0 utilizzando la formula di Hargreaves
    temperature_max = hourly_temperature_2m.max()  # Temperatura massima
    temperature_min = hourly_temperature_2m.min()  # Temperatura minima
    temperature_mean = (temperature_max + temperature_min) / 2  # Temperatura media

    # Calcolo della radiazione solare stimata
    solar_radiation = estimate_solar_radiation(latitude, end_date)

    et0 = 0.0023 * (temperature_mean + 17.8) * (temperature_max - temperature_min) ** 0.5 * solar_radiation

    return et0

def estimate_solar_radiation(latitude, date):
    # Formula di Angström-Prescott per la radiazione solare stimata
    # Coefficienti della formula di Angström-Prescott
    a = 0.25  # Coefficiente di trasparenza atmosferica
    b = 0.50  # Coefficiente di trasmissività atmosferica

    # Calcolo della durata del giorno in ore
    day_length_hours = calculate_day_length(latitude, date)

    # Calcolo della radiazione solare stimata
    estimated_radiation = a + b * day_length_hours

    return estimated_radiation

def calculate_day_length(latitude, date):
    # Calcola la durata del giorno utilizzando la libreria ephem
    obs = ephem.Observer()
    obs.lat = str(latitude)
    obs.lon = '0'  # Utilizza longitudine zero per semplificare il calcolo
    obs.date = date.strftime('%Y/%m/%d')

    sun = ephem.Sun()
    sunrise = obs.previous_rising(sun).datetime()
    sunset = obs.next_setting(sun).datetime()

    # Calcola la durata del giorno in ore
    day_length_hours = (sunset - sunrise).total_seconds() / 3600

    return day_length_hours

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

def calculate_gdd(temperature_mean, card_min):
    if temperature_mean > card_min:
        return temperature_mean - card_min
    else:
        return 0

def calculate_accumulated_gdd(temperature_data, card_min):
    print(temperature_data)
    accumulated_gdd = 0
    for temperature_max, temperature_min in temperature_data:
        print(temperature_max)
        print(temperature_min)
        temperature_mean = (temperature_max + temperature_min) / 2
        accumulated_gdd += calculate_gdd(temperature_mean, card_min)
    return accumulated_gdd


def calculate_and_show_et0():
    try:
        # Get user input
        crop_selection = crop_combo.get()  # Get selected crop
        planting_date = calendar.selection_get()

        # Get real GPS coordinates
        latitude, longitude = get_real_gps_coordinates()

        # Calculate end date (current date)
        end_date = datetime.now()

        # Get temperature range and card_min for selected crop
        temperature_max, temperature_min = get_temperature_range_for_crop(crop_selection)
        card_min = temperature_min

        # Calculate ET0
        et0 = calculate_et0(latitude, longitude, planting_date, end_date)
        
        # Calculate accumulated growing degree days (GDD)
        temperature_data = [(temperature_max, temperature_min)]  
        accumulated_gdd = calculate_accumulated_gdd(temperature_data, card_min)

        # Estimate phenological stage
        estimated_stage = estimate_phenological_stage(crop_selection, accumulated_gdd)

        # Calculate Kc
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

        # Calculate estimated evapotranspiration (ET) using Kc
        et_stimata = et0 * kc

        # Display results in a more informative format
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
