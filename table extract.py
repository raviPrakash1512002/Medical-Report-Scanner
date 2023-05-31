import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QFileDialog
from PIL import Image
import io
import boto3
import pandas as pd

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.title = 'Table Extractor'
        self.left = 100
        self.top = 100
        self.width = 640
        self.height = 480

        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        # create a label to display instructions
        self.label = QLabel(self)
        self.label.setText('Select an image or pdf file:')
        self.label.move(20, 20)

        # create a button to select a file
        self.button = QPushButton('Select File', self)
        self.button.move(20, 50)
        self.button.clicked.connect(self.selectFile)

        # create a button to process the file
        self.processButton = QPushButton('Process File', self)
        self.processButton.move(20, 80)
        self.processButton.setEnabled(False)
        self.processButton.clicked.connect(self.processFile)

    def selectFile(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self,"Select File", "","All Files (*);;PDF Files (*.pdf);;Image Files (*.jpg *.jpeg *.png *.bmp)", options=options)
        if fileName:
            self.filePath = fileName
            self.label.setText(f'Selected file: {fileName}')
            self.processButton.setEnabled(True)

    def processFile(self):
        session = boto3.Session(
            aws_access_key_id='AKIATTWE4TOCJJKUAIV5',
            aws_secret_access_key='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',
            region_name='ap-south-1'
        )
        client = session.client('textract')

        if self.filePath.lower().endswith('.pdf'):
            with open(self.filePath, 'rb') as f:
                pdf_bytes = f.read()
            response = client.analyze_document(Document={'Bytes': pdf_bytes}, FeatureTypes=['TABLES'])
        else:
            im = Image.open(self.filePath)
            buffered = io.BytesIO()
            im.save(buffered, format='PNG')
            response = client.analyze_document(Document={'Bytes': buffered.getvalue()}, FeatureTypes=['TABLES'])
        


            
        def map_blocks(blocks, block_type):
            return {
                block['Id']: block
                for block in blocks
                if block['BlockType'] == block_type
            }

        blocks = response['Blocks']
        tables = map_blocks(blocks, 'TABLE')
        cells = map_blocks(blocks, 'CELL')
        words = map_blocks(blocks, 'WORD')
        selections = map_blocks(blocks, 'SELECTION_ELEMENT')

        def get_children_ids(block):
            for rels in block.get('Relationships', []):
                if rels['Type'] == 'CHILD':
                    yield from rels['Ids']




        dataframes = []


        for table in tables.values():

            # Determine all the cells that belong to this table
            table_cells = [cells[cell_id] for cell_id in get_children_ids(table)]
        
            # Determine the table's number of rows and columns
            n_rows = max(cell['RowIndex'] for cell in table_cells)
            n_cols = max(cell['ColumnIndex'] for cell in table_cells)
            content = [[None for _ in range(n_cols)] for _ in range(n_rows)]
            
            # Fill in each cell
            for cell in table_cells:
                cell_contents = [
                    words[child_id]['Text']
                    if child_id in words
                    else selections[child_id]['SelectionStatus']
                    for child_id in get_children_ids(cell)
                ]
                i = cell['RowIndex'] - 1
                j = cell['ColumnIndex'] - 1
                content[i][j] = ' '.join(cell_contents)

            # We assume that the first row corresponds to the column names
            dataframe = pd.DataFrame(content[1:], columns=content[0])
            dataframes.append(dataframe)
    







        for i, df in enumerate(dataframes):
            normal_range_col = None
            result_col = None
            
            # Find columns named 'normal range' and 'result'
            for col in df.columns:
                if col.lower() == 'normal range':
                    normal_range_col = col
                elif col.lower() == 'result':
                    result_col = col
                    
            # If normal range and result columns exist, create a new column named 'result within range'
            if normal_range_col and result_col:
                # Define a function to check if a result value is within the normal range
                def within_range(normal_range, result):
                
                    if isinstance(normal_range, str):
                        # Handle different types of normal range values
                        if normal_range.startswith('<'):
                            return float(result) < float(normal_range[1:])
                        elif normal_range.startswith('>'):
                            return float(result) > float(normal_range[1:])
                        elif normal_range.startswith('Up to'):
                        
                            return float(result) <= float(normal_range[6:]) 
                        elif normal_range.startswith('less than'):
                            return float(result) < float(normal_range[10:])
                        elif normal_range.startswith('greater than'):
                            return float(result) > float(normal_range[13:])
                        else: 
                            return float(normal_range.split('-')[0]) <= float(result) <= float(normal_range.split('-')[1])
                df['result within range'] = df.apply(lambda row: 
                    within_range( row[normal_range_col], row[result_col]),axis=1)
                

                # Remove rows where 'result within range' is False
                df.drop(df[df['result within range']].index, inplace=True)
                df.drop(columns=['result within range'], inplace=True)
            
            with pd.ExcelWriter(f'data{i+1}_updated.xlsx') as writer:
                df.to_excel(writer, sheet_name=f'Table {i+1}', index=False)












if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())




