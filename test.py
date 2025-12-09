from processing.test import ReceiptSplitter
from utils.utils import cv_imread_chinese

t = ReceiptSplitter({})
t.split(cv_imread_chinese("C:/Users/tange/OneDrive/Desktop/all project/py for NKNU GA/input/燕巢小宏遠3.1.png"), debug=True)
