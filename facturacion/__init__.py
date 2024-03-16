import datetime
import logging
import azure.functions as func
import requests
import json

# Configuración y constantes
URL_HOSTAWAY_TOKEN = "https://api.hostaway.com/v1/accessTokens"
URL_HOLDED_INVOICE = "https://api.holded.com/api/invoicing/v1/documents/invoice"
SERIE_FACTURACION_DEFAULT = "Alojamientos"
IVA_DEFAULT = 0.21
PARAMETRO_A_ID = {
    "Rocio": "65d9f06600a829a27305f066s",
    "Alojamientos": "65d9f0e90396551d79088219",
    "Efectivo": "62115e5292bee258e53a6756",
}

def obtener_acceso_hostaway():
    try:
        payload = {
            "grant_type": "client_credentials",
            "client_id": "81585",
            "client_secret": "0e3c059dceb6ec1e9ec6d5c6cf4030d9c9b6e5b83d3a70d177cf66838694db5f",
            "scope": "general"
        }
        headers = {'Content-type': "application/x-www-form-urlencoded", 'Cache-control': "no-cache"}
        response = requests.post(URL_HOSTAWAY_TOKEN, data=payload, headers=headers)
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.RequestException as e:
        logging.error(f"Error al obtener el token de acceso: {str(e)}")
        raise

def determinar_serie_y_iva(reserva):
    serie_facturacion = SERIE_FACTURACION_DEFAULT
    iva = IVA_DEFAULT
    custom_fields = reserva.get("customFieldValues", [])
    
    for field in custom_fields:
        if field["customField"]["name"] == "Serie Facturas":
            serie_facturacion = field["value"]
        if serie_facturacion == "Rocio":
            iva = 0
            break
    
    return serie_facturacion, iva

def comprobar_si_existe_factura(reserva):
    custom_fields = reserva["customFieldValues"]
    for field in custom_fields:
        if field["customField"]["name"] == "holdedID":
            if field["value"] == "Ya esta facturada":
                return True
    return False
            
    

def crear_factura(reserva, serie_facturacion, iva):
    try:
        now = datetime.datetime.now()
        timestamp = int(now.timestamp())
        serie_id = PARAMETRO_A_ID.get(serie_facturacion, PARAMETRO_A_ID[SERIE_FACTURACION_DEFAULT])
        payload = {
            "applyContactDefaults": True,
            "items": [{
                "tax": iva * 100,
                "name": f"{reserva['listingName']} - {reserva['arrivalDate']} a {reserva['departureDate']}",
                "subtotal": str(reserva["totalPrice"] / (1 + iva))
            }],
            "currency": reserva["currency"],
            "date": timestamp,
            "numSerieId": serie_id,
            "contactName": reserva["guestName"]
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "key": "260f9570fed89b95c28916dee27bc684"
        }
        response = requests.post(URL_HOLDED_INVOICE, json=payload, headers=headers)
        response.raise_for_status()
        return response.status_code, response.json(), payload
    except requests.RequestException as e:
        logging.error(f"Error al crear la factura: {str(e)}")
        raise
 
def marcarComoFacturada(reserva,token):
    try:
        
        reserva_id = str(reserva["hostawayReservationId"])
        url = f"https://api.hostaway.com/v1/reservations/{reserva_id}"
        headers = {
            'Authorization': f"Bearer {token}",
            'Content-type': "application/json",
            'Cache-control': "no-cache",
        }

        custom_fields = reserva["customFieldValues"]
        for field in custom_fields:
            if field["customField"]["name"] == "holdedID":
                field["value"] = "Ya esta facturada"
                break
        
        response = requests.put(url, json=reserva, headers=headers)
        response.raise_for_status()  # Esto lanzará un error si el código de estado es >= 400
        return "Marca como facturada exitosamente."
    except requests.RequestException as e:
        error_msg = f"Error al marcar como facturada: {e}"
        logging.error(error_msg)
        return error_msg

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Azure HTTP trigger function processed a request.')
    payload=""
    try:
        if req.get_json().get("object")!="reservation":
            return func.HttpResponse("Solo procesa eventos de reserva", status_code=200)
        reserva = req.get_json().get("data", {})
        if reserva == "test":
            return func.HttpResponse("Test Succesfull", status_code=200)
        if reserva.get("paymentStatus") != "Paid":
            return func.HttpResponse("La factura no se genera hasta que no se completa el pago", status_code=200)
        
        if comprobar_si_existe_factura(reserva):
            return func.HttpResponse("Factura ya existente", status_code=200)
        
        serie_facturacion, iva = determinar_serie_y_iva(reserva)
        resultado_crear_factura, factura_info,payload = crear_factura(reserva, serie_facturacion, iva)
        access_token = obtener_acceso_hostaway()
        marcarComoFacturada(reserva, access_token)
        
        return func.HttpResponse(f"Factura creada correctamente: {factura_info}", status_code=resultado_crear_factura)
    except Exception as e:
        logging.error(f"Error en la función: {str(e)}")
        return func.HttpResponse(f"Error interno del servidor: {str(e)} {payload} ", status_code=500)
