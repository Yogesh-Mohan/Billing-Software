import os
import pandas as pd
import sys

# Add current directory to path so we can import from app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app import db

def import_events():
    file_path = "Redwed ledger.xlsx"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Reading {file_path} (sheet: orders)...")
    try:
        df = pd.read_excel(file_path, sheet_name='orders', header=1) 
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    events = []
    current_event = {}
    
    # Iterate rows and extract data
    for index, row in df.iterrows():
        serial = row.get('Serial.No')
        name = row.get('Name')
        
        def get_clean_val(col_name):
            val = row.get(col_name)
            if pd.isna(val): return ""
            s = str(val).strip()
            if s.endswith('.0') and col_name == 'Client Number':
                s = s[:-2]
            return s
        
        # If we have a new Serial.No, start a new event
        if pd.notna(serial) and str(serial).strip() != "":
            if current_event:
                events.append(current_event)
            
            # Clean up name (remove newlines, extra spaces)
            clean_name = str(name).replace('\n', ' ').strip() if pd.notna(name) else "Unknown Customer"

            current_event = {
                "serial_no": get_clean_val('Serial.No'),
                "customer_name": clean_name,
                "date": get_clean_val('Date'),
                "acquisition": get_clean_val('  Acquisition'),
                "event_type": get_clean_val('Event Type'),
                "package": get_clean_val('Package'),
                "budget": get_clean_val('Budget'),
                "booking_date": get_clean_val('Booking Date'),
                "venue": get_clean_val('Venue'),
                "payment": get_clean_val('Payment'),
                "pending": get_clean_val('Pending'),
                "client_number": get_clean_val('Client Number'),
                "client_address": get_clean_val('Client Adress')
            }
        else:
            # It's a continuation row for the current event
            if current_event:
                for field, col in [
                    ("date", "Date"),
                    ("acquisition", "  Acquisition"),
                    ("event_type", "Event Type"),
                    ("package", "Package"),
                    ("budget", "Budget"),
                    ("booking_date", "Booking Date"),
                    ("venue", "Venue"),
                    ("payment", "Payment"),
                    ("pending", "Pending"),
                    ("client_number", "Client Number"),
                    ("client_address", "Client Adress")
                ]:
                    val = get_clean_val(col)
                    if val:
                        if current_event[field]:
                            current_event[field] += "\n" + val
                        else:
                            current_event[field] = val
            
    # Add the last event
    if current_event:
        events.append(current_event)
        
    print(f"Found {len(events)} events. Inserting into database...")
    
    # Clear existing to avoid duplicates if run multiple times
    try:
        if hasattr(db.events, 'delete_many'):
            db.events.delete_many({})
        elif hasattr(db.events, '_write'):
            db.events._write([])
    except Exception as e:
        print(f"Could not clear existing events: {e}")
    
    inserted = 0
    for ev in events:
        try:
            db.events.insert_one(ev)
            inserted += 1
        except Exception as e:
            print(f"Error inserting event {ev.get('serial_no')}: {e}")
            
    print(f"Import completed successfully! Inserted {inserted} records.")

if __name__ == '__main__':
    import_events()
