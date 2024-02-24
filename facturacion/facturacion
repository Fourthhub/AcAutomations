import requests

url = "https://api.holded.com/api/invoicing/v1/documents/invoice"


import requests
import datetime

def crearFactura(reserva):
    # Convertir la fecha de reserva a timestamp
    
    now = datetime.datetime.now()
    timestamp = int(datetime.datetime.timestamp(now))

    payload = {
        "applyContactDefaults": True,
        "items": [
            {
                "name": f"{reserva['listingName']} - {reserva['arrivalDate']} a {reserva['departureDate']}",
                "subtotal": str(reserva["totalPrice"])
            }
        ],
        "currency": reserva["currency"],
        "date": timestamp,  # Uso de timestamp de la fecha de reserva
        #"numSerieId": "Rocio",
        "contactName": reserva["guestName"]  # Uso del nombre del huésped
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "key": "260f9570fed89b95c28916dee27bc684"
    }

    response = requests.post(url, json=payload, headers=headers)

    return response.status_code

# Asegúrate de reemplazar 'reserva' con el objeto de tu reserva real al llamar a la función

    