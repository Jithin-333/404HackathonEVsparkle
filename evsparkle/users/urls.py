from django.contrib import admin
from django.urls import path,include
from.import views

urlpatterns = [
    path('', views.home, name = 'home'),
    path('ev-map/', views.ev_charging_map, name='ev_charging_map'),

    
    # API endpoints
    path('api/charging-stations/', views.get_charging_stations_api, name='charging_stations_api'),

    path("api/predict_best_station/", views.predict_best_station_api, name="predict_best_station_api"),

]

