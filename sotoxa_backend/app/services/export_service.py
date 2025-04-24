import csv
import io
import xlsxwriter
from typing import List, Dict
from datetime import datetime

class ExportService:
    @staticmethod
    async def generate_csv(results: List[Dict]) -> bytes:
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            "Test ID", "Person ID", "Operator", "Test Date", "Status",
            "OCR Confidence", "Location", "Drug Types", "Results"
        ]
        writer.writerow(headers)
        
        # Write data
        for result in results:
            row = [
                str(result["_id"]),
                result["person_id"],
                result["operator"]["name"],
                result["test_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                result["processing_status"],
                f"{result['ocr_confidence']:.2f}%",
                f"{result['location']['latitude']}, {result['location']['longitude']}" if result.get('location') else "N/A",
                ", ".join(result["ocr_data"].keys()),
                ", ".join(f"{k}: {v}" for k, v in result["ocr_data"].items())
            ]
            writer.writerow(row)
        
        return output.getvalue().encode('utf-8')

    @staticmethod
    async def generate_excel(results: List[Dict]) -> bytes:
        output = io.BytesIO()
        workbook = None
        try:
            workbook = xlsxwriter.Workbook(output)
            worksheet = workbook.add_worksheet()
            
            # Add formats
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#4F81BD',
                'font_color': 'white'
            })
            
            date_format = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm:ss'})
            
            # Write headers
            headers = [
                "Test ID", "Person ID", "Operator", "Test Date", "Status",
                "OCR Confidence", "Location", "Drug Types", "Results"
            ]
            for col, header in enumerate(headers):
                worksheet.write(0, col, header, header_format)
            
            # Write data
            max_lengths = [len(header) for header in headers]  # Initialize with header lengths
            
            for row, result in enumerate(results, start=1):
                # Prepare row data
                row_data = [
                    str(result["_id"]),
                    result["person_id"],
                    result["operator"]["name"],
                    result["test_timestamp"],
                    result["processing_status"],
                    f"{result['ocr_confidence']:.2f}%",
                    f"{result['location']['latitude']}, {result['location']['longitude']}" 
                    if result.get('location') else "N/A",
                    ", ".join(result["ocr_data"].keys()),
                    ", ".join(f"{k}: {v}" for k, v in result["ocr_data"].items())
                ]
                
                # Write row and track maximum lengths
                for col, value in enumerate(row_data):
                    if col == 3:  # Date column
                        worksheet.write_datetime(row, col, value, date_format)
                        max_lengths[col] = max(max_lengths[col], 20)  # Fixed width for dates
                    else:
                        worksheet.write(row, col, value)
                        max_lengths[col] = max(max_lengths[col], len(str(value)))
            
            # Set optimal column widths with some padding
            for col, max_length in enumerate(max_lengths):
                width = min(max(max_length + 2, 8), 50)
                worksheet.set_column(col, col, width)
            
            workbook.close()
            return output.getvalue()
            
        except Exception as e:
            if workbook:
                try:
                    workbook.close()
                except:
                    pass  # Ignore errors during emergency closure
            raise Exception(f"Failed to generate Excel file: {str(e)}")
        finally:
            output.seek(0)

