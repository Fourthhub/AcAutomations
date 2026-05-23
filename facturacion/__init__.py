from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import time
import requests
import logging

import azure.functions as func

# --- Constantes y configuración ---
URL_HOLDED_INVOICE = "https://api.holded.com/api/invoicing/v1/documents/invoice"
URL_HOLDED_RECEIPT = "https://api.holded.com/api/invoicing/v1/documents/salesreceipt"
URL_HOSTAWAY_TOKEN = "https://api.hostaway.com/v1/accessTokens"

SERIE_FACTURACION_DEFAULT = "Alojamientos"
IVA_DEFAULT = Decimal("0.10")
HTTP_TIMEOUT = 30

PARAMETRO_A_ID = {
    "Rocio": "65d9f06600a829a27305f066",
    "Alojamientos": "65d9f0e90396551d79088219",
    "Efectivo": "62115e5292bee258e53a6756",
}

HOSTAWAY_CLIENT_ID = "81585"
HOSTAWAY_CLIENT_SECRET = "0e3c059dceb6ec1e9ec6d5c6cf4030d9c9b6e5b83d3a70d177cf66838694db5f"
HOLDED_API_KEY = "260f9570fed89b95c28916dee27bc684"
HOLDED_API_KEY_RECEIPT = "2ed3f9bfff52da560e2c7826fe30f6c1"


# --- Helper con reintentos/backoff ---
def _request(method, url, *, max_retries=3, backoff_base=1.5, **kwargs):
    for attempt in range(max_retries + 1):
        resp = requests.request(method, url, timeout=HTTP_TIMEOUT, **kwargs)
        if resp.status_code in (429,) or 500 <= resp.status_code < 600:
            if attempt < max_retries:
                time.sleep(backoff_base ** attempt)
                continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()


# --- Auth Hostaway ---
def obtener_acceso_hostaway():
    try:
        payload = {
            "grant_type": "client_credentials",
            "client_id": HOSTAWAY_CLIENT_ID,
            "client_secret": HOSTAWAY_CLIENT_SECRET,
            "scope": "general"
        }
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "Cache-control": "no-cache"
        }
        response = requests.post(URL_HOSTAWAY_TOKEN, data=payload, headers=headers, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        token = response.json()["access_token"]
        logging.info("Token de Hostaway obtenido con éxito.")
        return token
    except requests.RequestException as e:
        logging.error(f"Error al obtener el token de acceso de Hostaway: {str(e)}")
        raise


# --- Chequeo si ya está facturada ---
def comprobar_si_existe_factura(reserva):
    for field in (reserva.get("customFieldValues") or []):
        if field.get("customFieldId") == 56844:
            return field.get("value") == "Ya esta facturada"
    return False


# --- Chequeo de fecha: solo facturar el día de llegada o después ---
def comprobar_fecha(reserva):
    fecha_checkin = reserva.get("arrivalDate")
    fecha_checkin_dt = datetime.strptime(fecha_checkin, "%Y-%m-%d").date()
    fecha_actual = datetime.now().date()
    return fecha_actual < fecha_checkin_dt  # True = aún no ha llegado el día


# --- Determinar serie e IVA ---
def determinar_serie_y_iva(reserva, token):
    serie_facturacion = SERIE_FACTURACION_DEFAULT
    iva = IVA_DEFAULT

    reserva_id = str(reserva.get("hostawayReservationId"))
    url = f"https://api.hostaway.com/v1/guestPayments/charges?reservationId={reserva_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json",
        "Cache-control": "no-cache",
    }
    data = _request("GET", url, headers=headers).json() or {}
    result = data.get("result") or []
    payment_method = result[0].get("paymentMethod") if result else None
    if payment_method == "cash":
        return "Efectivo", Decimal("0.00")

    for field in (reserva.get("customFieldValues") or []):
        if field.get("customFieldId") == 57829:
            if field.get("value"):
                serie_facturacion = field["value"]

    if serie_facturacion == "Rocio":
        iva = Decimal("0.00")

    return serie_facturacion, iva


# --- Obtener propietario del listing ---
def obtener_contact_name_listing(reserva, token):
    listing_id = reserva.get("listingMapId")
    if not listing_id:
        raise ValueError(f"Reserva {reserva.get('hostawayReservationId')} no tiene listingMapId")

    url = f"https://api.hostaway.com/v1/listings/{listing_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-type": "application/json",
        "Cache-control": "no-cache",
    }
    r = _request("GET", url, headers=headers)
    contact_name = r.json()["result"]["contactName"]
    logging.info(f"[obtener_contact_name_listing] listingMapId={listing_id} -> contactName={contact_name}")
    return contact_name


# --- Marcar reserva como facturada ---
def marcarComoFacturada(reserva, token):
    try:
        reserva_id = str(reserva.get("hostawayReservationId"))
        url = f"https://api.hostaway.com/v1/reservations/{reserva_id}?forceOverbooking=1"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-type": "application/json",
            "Cache-control": "no-cache",
        }
        payload = {"customFieldValues": [{"customFieldId": 56844, "value": "Ya esta facturada"}]}

        response = requests.put(url, json=payload, headers=headers, timeout=HTTP_TIMEOUT)
        logging.info(f"[marcarComoFacturada] Status: {response.status_code} | Body: {response.text}")
        response.raise_for_status()
        return "Marcada como facturada."

    except requests.HTTPError as e:
        logging.error(f"[marcarComoFacturada] HTTP {e.response.status_code}: {e.response.text}")
        return f"Error al marcar como facturada: {e}"
    except requests.RequestException as e:
        logging.error(f"[marcarComoFacturada] Request error: {e}")
        return f"Error al marcar como facturada: {e}"


# --- Crear factura en Holded ---
def crear_factura(reserva, serie_facturacion, iva):
    try:
        timestamp_seconds = int(datetime.now().timestamp())
        serie_id = PARAMETRO_A_ID.get(serie_facturacion, PARAMETRO_A_ID[SERIE_FACTURACION_DEFAULT])

        total = Decimal(str(reserva.get("totalPrice", 0)))
        base = (total / (Decimal("1") + iva)).quantize(Decimal("0.01"), ROUND_HALF_UP) if iva > 0 else total.quantize(Decimal("0.01"), ROUND_HALF_UP)
        tax_pct = int((iva * 100).quantize(Decimal("1")))

        payload = {
            "applyContactDefaults": True,
            "items": [{
                "tax": tax_pct,
                "name": f"{reserva.get('listingName', '')} - {reserva.get('arrivalDate', '')} a {reserva.get('departureDate', '')}",
                "subtotal": str(base),
            }],
            "currency": reserva.get("currency", "EUR"),
            "date": timestamp_seconds,
            "numSerieId": serie_id,
            "approveDoc": False,
            "contactName": reserva.get("guestName", "Huésped"),
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "key": HOLDED_API_KEY,
        }
        r = _request("POST", URL_HOLDED_INVOICE, json=payload, headers=headers)
        return r.status_code, r.json()
    except requests.RequestException as e:
        logging.error(f"Error al crear la factura: {e}")
        raise


# --- Generar recibo en Holded (para serie Rocio) ---
def generarRecibo(propietario, reserva, serie_facturacion, iva):
    try:
        timestamp_seconds = int(datetime.now().timestamp())
        serie_id = PARAMETRO_A_ID.get(serie_facturacion, PARAMETRO_A_ID[SERIE_FACTURACION_DEFAULT])

        total = Decimal(str(reserva.get("totalPrice", 0)))
        base = (total / (Decimal("1") + iva)).quantize(Decimal("0.01"), ROUND_HALF_UP) if iva > 0 else total.quantize(Decimal("0.01"), ROUND_HALF_UP)
        tax_pct = int((iva * 100).quantize(Decimal("1")))

        payload = {
            "applyContactDefaults": False,
            "contactName": propietario.upper(),
            "items": [{
                "tax": tax_pct,
                "name": f"{reserva.get('guestName', '')} {reserva.get('listingName', '')} - {reserva.get('arrivalDate', '')} a {reserva.get('departureDate', '')}",
                "subtotal": str(base),
            }],
            "currency": reserva.get("currency", "EUR"),
            "notes": "Adarena Stays S.L (Apartamentos Cantabria) interviene exclusivamente como mandatario e intermediario en la gestión de cobros y reservas del inmueble objeto de alquiler turístico, actuando en nombre y por cuenta del propietario, quien ostenta la condición de prestador del servicio a efectos contractuales y fiscales.",
            "date": timestamp_seconds,
            "numSerieId": serie_id,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "key": HOLDED_API_KEY_RECEIPT,
        }
        r = _request("POST", URL_HOLDED_RECEIPT, json=payload, headers=headers)
        return r.status_code, r.json()
    except requests.RequestException as e:
        logging.error(f"Error al generar el recibo: {e}")
        raise


# --- Entry point Queue Trigger ---
def main(msg: func.QueueMessage) -> None:
    logging.info("Queue trigger procesando mensaje.")

    try:
        body = msg.get_body().decode("utf-8")
        data = json.loads(body) if isinstance(body, str) else body

        if data.get("object") != "reservation":
            logging.info("Mensaje ignorado: no es una reserva.")
            return

        reserva = data.get("data", {})

        if reserva == "test":
            logging.info("Mensaje de test recibido.")
            return

        rid = reserva.get("hostawayReservationId")
        logging.info(f"{rid} - Procesando reserva...")

        if reserva.get("status") == "cancelled":
            logging.info(f"{rid} - Reserva cancelada, saltando.")
            return

        if reserva.get("paymentStatus") != "Paid":
            logging.info(f"{rid} - No está pagada aún.")
            return

        if reserva.get("totalPrice", 0) == 0:
            logging.info(f"{rid} - Total 0€, no se genera factura.")
            return

        if comprobar_si_existe_factura(reserva):
            logging.info(f"{rid} - Ya existe la factura.")
            return

        if comprobar_fecha(reserva):
            logging.info(f"{rid} - Aún no es el día de llegada, se facturará entonces.")
            return

        if not reserva.get("listingMapId"):
            logging.warning(f"{rid} - Sin listingMapId, saltando.")
            return

        access_token = obtener_acceso_hostaway()
        serie_facturacion, iva = determinar_serie_y_iva(reserva, access_token)

        if serie_facturacion == "Rocio":
            propietario = obtener_contact_name_listing(reserva, access_token)
            status, factura_info = generarRecibo(propietario, reserva, serie_facturacion, iva)
        else:
            status, factura_info = crear_factura(reserva, serie_facturacion, iva)

        logging.info(f"{rid} - Respuesta Holded: status={status} info={factura_info}")

        if 200 <= status < 300:
            resultado = marcarComoFacturada(reserva, access_token)
            logging.info(f"{rid} - Documento generado en Holded. Marcado: {resultado}")
        else:
            logging.error(f"{rid} - Error en respuesta de Holded: status={status} info={factura_info}")

    except Exception as e:
        logging.error(f"Error en la función de cola: {e}")
        raise
