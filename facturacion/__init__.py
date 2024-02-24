import datetime
import logging
import azure.functions as func
import requests
import http.client
import json  # Importa el módulo json para procesar el cuerpo de la solicitud

conn = http.client.HTTPSConnection("api.hostaway.com")
url = "https://api.holded.com/api/invoicing/v1/documents/invoice"
#Por defecto va a la serie Alojamientos
serieFacturacion = "Alojamientos"
iva=0.21
IdFactura=None

#Mapeo de nombres de series y su ID
parametro_a_id = {
    "Rocio": "65d9f06600a829a27305f066s",
    "Alojamientos": "65d9f0e90396551d79088219",
    "Efectivo": "62115e5292bee258e53a6756",
}

def determinarSerie(reserva):
    custom_fields = reserva["customFieldValues"]
       
    for field in custom_fields:
        if field["customField"]["name"] == "Serie Facturas":
            serieFacturacion = field["value"]
            break
    if serieFacturacion=="Rocio":
        iva=0
    
    return serieFacturacion


def comprobarSiExisteFactura(reserva):
    custom_fields = reserva["customFieldValues"]
    for field in custom_fields:
        if field["customField"]["name"] == "HoldedID":
            idFactura = field["value"]
            break
    if IdFactura != None:
        return True
    else: return False

def obtener_acceso_hostaway():
    
    payload = "grant_type=client_credentials&client_id=81585&client_secret=0e3c059dceb6ec1e9ec6d5c6cf4030d9c9b6e5b83d3a70d177cf66838694db5f&scope=general"
    headers = {'Content-type': "application/x-www-form-urlencoded", 'Cache-control': "no-cache"}
    conn.request("POST", "/v1/accessTokens", payload, headers)
    res = conn.getresponse()
    data = res.read()
    return data.decode("utf-8")

def marcarComoFacturada(reserva):
    bearer = obtener_acceso_hostaway()
    custom_fields = reserva["customFieldValues"]
    for field in custom_fields:
        if field["customField"]["name"] == "HoldedID":
            field["value"] = "Ya esta facturada"
            break
    
    payload_json = json.dumps(reserva)

    headers = {
        'Authorization': "Bearer "+bearer,
        'Content-type': "application/json",
        'Cache-control': "no-cache",
    }


    conn.request("PUT", "v1/reservations/"+reserva["hostawayReservationId"], payload_json, headers)

    res = conn.getresponse()
    data = res.read()

    

def crearFactura(reserva):

    now = datetime.datetime.now()
    timestamp = int(datetime.datetime.timestamp(now))
    serieFacturacion = parametro_a_id[determinarSerie(reserva)]
    payload = {
        "applyContactDefaults": True,
        "items": [
            {
                "tax": (iva*100),
                "name": f"{reserva['listingName']} - {reserva['arrivalDate']} a {reserva['departureDate']}",
                "subtotal": str((reserva["totalPrice"]/(1+iva)))
            }
        ],
        "currency": reserva["currency"],
        "date": timestamp,  # Uso de timestamp de la fecha de reserva
        "numSerieId": serieFacturacion,
        "contactName": reserva["guestName"]  # Uso del nombre del huésped
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "key": "260f9570fed89b95c28916dee27bc684"
    }

    response = requests.post(url, json=payload, headers=headers)
    
    return response.status_code

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Intenta obtener el cuerpo de la solicitud y convertirlo de JSON a un diccionario de Python
        reserva = req.get_json()["data"]
        
        
    except ValueError:
        # Si hay un error al interpretar el JSON, devuelve un error
        return func.HttpResponse(
            "El json enviado no contiene el objeto data",
            status_code=400
        )
    else:    
        
        
        # Comprobar que la factura esta pagada y que no se ha generado previamente
        try:
            if(reserva["paymentStatus"]!="Paid"):
                return func.HttpResponse(f"La factura no se genera hasta que no se completa el pago",
            status_code=200)
        
            if(comprobarSiExisteFactura(reserva)):
                return  func.HttpResponse(f"Factura ya existente", status_code=200)
            
            
            resultado = crearFactura(reserva)
            marcarComoFacturada(reserva)
        except Exception as e:
            return  func.HttpResponse(str(e)
            ,
            status_code=400)

        
        return func.HttpResponse(
            f"Factura creada correctamente +" + str(resultado),
            status_code=200
        )
        
