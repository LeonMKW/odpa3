# -*- coding: UTF-8 -*-
import pandas as pd
import pymongo
import math


# altitude in km
def calculate_orbit_period(altitude):
    # Convert altitude from kilometers to meters
    altitude *= 1000

    # Gravitational constant (m^3/kg/s^2)
    G = 6.674 * 10 ** -11

    # Radius of the central body (Earth) in meters
    central_body_radius = 6371 * 1000  # Earth's mean radius in meters

    # Semi-major axis of the orbit (average distance from satellite to center of Earth)
    semi_major_axis = altitude + central_body_radius

    # Calculate the period of the orbit using Kepler's Third Law
    period_seconds = 2 * math.pi * math.sqrt((semi_major_axis ** 3) / (G * 5.972e24))

    # Convert period from seconds to minutes and hours
    period_minutes = period_seconds / 60
    period_hours = period_minutes / 60

    return period_minutes

# # Example usage
# altitude_km = 500  # Altitude of the satellite in kilometers
# central_body_mass_kg = 5.972e24  # Mass of the Earth in kilograms
#
# period_seconds, period_minutes, period_hours = calculate_orbit_period(altitude_km, central_body_mass_kg)
#
# print("Period of the satellite orbit:")
# print(f"Seconds: {period_seconds:.2f} s")
# print(f"Minutes: {period_minutes:.2f} min")
# print(f"Hours: {period_hours:.2f} hours")
