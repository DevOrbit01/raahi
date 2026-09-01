"""Convert property.csv to the scraper Excel format."""
import csv
import re
from datetime import datetime

from openpyxl import Workbook


MAX_CELL_LENGTH = 32000


def clean_html(text):
    """Remove HTML tags from text and handle NULL values."""
    if not text or text == "NULL":
        return ""
    text = re.sub(r"<[^>]+>", "", str(text))
    return " ".join(text.split()).strip()


def safe_excel_value(value):
    """Return a value that openpyxl can safely write into a cell."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    if len(text) > MAX_CELL_LENGTH:
        text = text[:MAX_CELL_LENGTH]
    return text


def convert_date(date_str):
    """Convert YYYY-MM-DD or DD-MM-YYYY-like dates to DD-MM-YYYY format."""
    if not date_str or date_str in {"NULL", "0000-00-00"}:
        return ""

    date_str = str(date_str).strip()
    try:
        date_part = date_str.split()[0]
        separator = "-" if "-" in date_part else "/" if "/" in date_part else None
        if not separator:
            return date_str

        parts = date_part.split(separator)
        if len(parts) != 3:
            return date_str

        first, second, third = parts
        if len(first) == 4:
            year, month, day = first, second, third
        else:
            day, month, year = first, second, third
        return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
    except Exception:
        return date_str


def convert_datetime(datetime_str):
    """Convert datetime to DD-MM-YYYY format, ignoring time."""
    if not datetime_str or datetime_str in {"0000-00-00 00:00:00", "NULL"}:
        return ""
    return convert_date(str(datetime_str).split()[0])


def clean_price(price_str):
    """Remove commas and convert to float."""
    if not price_str or price_str == "NULL":
        return 0
    try:
        cleaned = str(price_str).replace(",", "").strip()
        return float(cleaned) if cleaned else 0
    except Exception:
        return 0


def clean_value(value):
    return "" if not value or value == "NULL" else value


def build_upload_url(filename):
    if not filename or filename == "NULL":
        return ""
    return f"https://www.raahiauction.com/assets/uploads/property/{filename}"


def convert_csv_to_xlsx(csv_path, output_path=None):
    """
    Convert property.csv to the Excel columns used by the scraper.

    Args:
        csv_path: Path to input CSV file.
        output_path: Path to output XLSX file.
    """
    if not output_path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_path = f"converted_properties_{timestamp}.xlsx"

    print(f"[Converter] Reading CSV from: {csv_path}")

    properties = []
    with open(csv_path, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if not row.get("name") or not row.get("listing_id"):
                continue

            property_data = {
                "newListingId": clean_value(row.get("listing_id", "")),
                "schemeName": "",
                "name": clean_html(row.get("name", "")),
                "category": clean_value(row.get("asset_category", "")),
                "state": clean_value(row.get("state", "")),
                "city": clean_value(row.get("city", "")),
                "areaTown": clean_value(row.get("area", "")),
                "date": convert_date(row.get("auction_date", "")),
                "reservePrice": clean_price(row.get("reserved_price", "")),
                "emd": clean_price(row.get("emd_price", "")),
                "incrementBid": 0,
                "bankName": clean_value(row.get("institution", "")),
                "branchName": clean_value(row.get("institution_branch", "")),
                "contactDetails": clean_html(row.get("contact_details", "")),
                "description": clean_html(row.get("asset_address", "")),
                "address": "",
                "note": "",
                "borrowerName": "",
                "publishingDate": convert_date(row.get("publication_date", "")),
                "inspectionDate": convert_datetime(row.get("inspection_date_and_time", "")),
                "applicationSubmissionDate": convert_datetime(row.get("application_submission_deadline", "")),
                "auctionStartDate": convert_datetime(row.get("auction_date_time", "")),
                "auctionEndTime": convert_datetime(row.get("auction_end_date_time", "")),
                "auctionType": clean_value(row.get("auction_type", "")),
                "listingId": clean_value(row.get("listing_id", "")),
                "images": build_upload_url(row.get("photo1", "")),
                "notice": build_upload_url(row.get("pdf1", "")),
                "source": "property.csv",
                "url": "",
                "fingerprint": f"csv_{row.get('listing_id', '')}",
            }

            if property_data["date"]:
                properties.append(property_data)

    print(f"[Converter] Converted {len(properties)} properties")

    wb = Workbook()
    ws = wb.active
    ws.title = "Auctions"

    if properties:
        headers = list(properties[0].keys())
        ws.append(headers)
        for item in properties:
            ws.append([safe_excel_value(item.get(header, "")) for header in headers])

    wb.save(output_path)
    print(f"[Converter] Saved to: {output_path}")
    print(f"[Converter] Total properties: {len(properties)}")

    return output_path


if __name__ == "__main__":
    convert_csv_to_xlsx("property.csv")
