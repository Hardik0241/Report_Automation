def _apply_formatting(self, worksheet):
    # Define the format for the cell
    format = {'textFormat': {'fontFamily': 'Calibri', 'fontSize': 13}}
    # Apply the format to all cells in the worksheet
    range = f'A1:{worksheet.get_last_row_column()}'  # Adjust the range if necessary
    self.service.spreadsheets().batchUpdate(
        spreadsheetId=self.spreadsheet_id,
        body={
            'repeatCell': {
                'range': {
                    'sheetId': worksheet.sheet_id,
                    'startRowIndex': 0,
                    'startColumnIndex': 0,
                },
                'cell': {
                    'userEnteredFormat': format
                },
                'fields': 'userEnteredFormat.textFormat'
            }
        }
    ).execute()

    # Call the formatting method in other methods as needed
    # Example integration in the _create_worksheet method
    def _create_worksheet(self, title):
        # Logic for creating a worksheet
        worksheet = self.service.spreadsheets().create(...)
        self._apply_formatting(worksheet)
        return worksheet

    # Integration in ensure_date_for_all_employees
    def ensure_date_for_all_employees(self):
        # Logic to ensure date
        self._apply_formatting(self.worksheet)

    # Integration in write_data
    def write_data(self, data):
        # Logic to write data
        self._apply_formatting(self.worksheet)

    # Integration in mark_not_sent
    def mark_not_sent(self):
        # Logic to mark not sent
        self._apply_formatting(self.worksheet)
}
