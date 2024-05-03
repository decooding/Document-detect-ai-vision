import os
import re
import time
import asyncio
import tempfile
import numpy as np
from PIL import Image
import streamlit as st
from datetime import datetime
from selenium import webdriver
from google.cloud import vision
from pyzbar.pyzbar import decode
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

agree_getid = False
magican = True
magic_str = {}

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = './credentials.json'

def detect_text(image):
    text_list = []
    obj_list = []

    client = vision.ImageAnnotatorClient()
    image_content = image.read()

    image = vision.Image(content=image_content)
    obj_response = client.object_localization(image=image)
    objects = obj_response.localized_object_annotations
    text_response = client.text_detection(image=image)
    texts = text_response.text_annotations
    
    for text in texts:
        text_list.append(text.description)
    for obj in objects:
        obj_list.append(obj.name)
    return text_list, obj_list

async def getid(IIN):
    try:
        chromePath = 'S:/chromedriver.exe'

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--window-position=1400,0")  # позиция окна на втором мониторе
        chrome_options.add_argument("--window-size=800,800")   # размер окна

        driver = webdriver.Chrome(executable_path=chromePath,chrome_options=chrome_options)
        driver.get("https://nca.pki.gov.kz/service/pkiorder/create.xhtml;jsessionid=XsLTv517ojwgq2oztVHDiWGX4pbVZ6kYB4XFj9mQ.nca-alma-62?lang=ru&certtemplateAlias=individ_ng")

        checkbox = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "myCheckbox")))
        checkbox.click()

        button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "buttonAcceptAgreement")))
        button.click()
        element = driver.find_element(By.ID, "updatePanel_content")
        time.sleep(2)
        element.screenshot("./doc/screenshot.png")
        with Image.open("./doc/screenshot.png") as image:
            temp_image_path = tempfile.mkstemp(suffix=".png")[1]
            image.save(temp_image_path)
            with open(temp_image_path, "rb") as temp_image:
                capcha_list, _ = detect_text(temp_image)
                capcha = list(filter(lambda x: len(x) == 5, capcha_list))

        captcha_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='captcha']")))
        captcha_input.clear()
        captcha_input.send_keys(capcha)

        value_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='rcfield:0:inputValue']")))
        value_input.clear()
        value_input.send_keys(IIN)

        button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, "rcfield:0:checkPersonButton")))
        button.click()
        time.sleep(2)

        first_name_element = driver.find_element(By.ID, "rcfield:1:values")
        last_name_element = driver.find_element(By.ID, "rcfield:2:values")
        middle_name_element = driver.find_element(By.ID, "rcfield:3:values")

        first_name = first_name_element.text
        last_name = last_name_element.text
        middle_name = middle_name_element.text

        driver.quit() 
        await asyncio.sleep(2)
        return first_name, last_name, middle_name
    except Exception as e:
        return st.warning(f'Проверяемый ИИН {IIN}, указаный в Вашем запросе, не найден в Государственной Базе Данных Физических Лиц. Пожалуйста, укажите запрос с правильным ИИН.', icon="⚠️")

def detec_date(list_of_strings):
    matches = []
    birth_date = None
    IIN = None
    ID_DOC = None
    date_regex = r'\b(\d{2}\.\d{2}\.\d{4})\b'

    for text in list_of_strings:
        date_matches = re.findall(date_regex, text)
        matches.extend(date_matches)
        if text.isdigit() and len(text) == 12:
            IIN = text
            print("IIN: ", text)
            date_object = datetime.strptime(text[:6], "%y%m%d")
            birth_date = date_object.strftime("%d.%m.%y")
        elif text.isdigit() and len(text) >= 4:
            ID_DOC = text
            print("ID_DOC: ", text)
    if not matches:
        st.error('Не удалось найти дату на одной из сторон документа.')
        return
    
    dates_as_datetime = [datetime.strptime(date, '%d.%m.%Y') for date in matches]
    max_date = max(dates_as_datetime)
    max_date_formatted = max_date.strftime("%d.%m.%y")
    if birth_date != max_date_formatted:
        current_date = datetime.now()
        remaining_time = max_date - current_date
    
        if remaining_time.days > 0:
            years = remaining_time.days // 365
            months = (remaining_time.days % 365) // 30
            remaining_days = remaining_time.days - years * 365 - months * 30
            st.warning(f'СРОК ДОКУМЕНТА ЗАКОНЧИТСЯ ЧЕРЕЗ {years} года(лет), {months} месяца(ев), {remaining_days} дня(ей)', icon="❔")
        else:
            st.error('СРОК ДОКУМЕНТА ИСТЁК!', icon="⚠️")
    print("Max date: ", max_date_formatted, birth_date)
    return IIN, ID_DOC


def detect_barcode(image):
    image_np = np.array(Image.open(image))
    decoded_objects = decode(image_np)
    barcodes = []
    for obj in decoded_objects:
        barcodes.append(obj.data.decode("utf-8"))
    return barcodes[0] if barcodes else None


def check_edit(image):
    with Image.open(image) as img:
        metadata = img.info
        print("img.info: ", img.info)
        if "Software" in metadata:
            return metadata["Software"]
        else:
            return False

def detect_and_print_info(front_file, back_file, agree_getid):
    front_text_list, front_obj_list, = detect_text(front_file)
    back_text_list, back_obj_list, = detect_text(back_file)

    if detect_barcode(front_file) is not None:
      print('-' * 89)
      print("Front barcodes: ", detect_barcode(front_file))
    if detect_barcode(back_file) is not None:
      print('-' * 89)
      print("Back barcodes: ", detect_barcode(back_file))   
        
    print('-' * 89)
    print("front_text_list: ", front_text_list[1:])
    print("front_obj_list: ", front_obj_list)

    print('-' * 89)
    print("back_text_list: ", back_text_list[1:])
    print("back_obj_list: ", back_obj_list)

    if ('КУӘЛІК' in front_text_list and 'УДОСТОВЕРЕНИЕ' in front_text_list) and front_obj_list[0] == 'Person':
        st.toast('ДОКУМЕНТ ОПРЕДЕЛЕН: УДОСТОВЕРЕНИЕ ЛИЧНОСТИ', icon='✅')
        IINF, ID_DOCF = detec_date(front_text_list[1:])
        IINB, ID_DOCB = detec_date(back_text_list[1:])
        
        if detect_barcode(back_file) == IINF:
          st.success('ШТРИХ КОД ДЕЙСТВИТЕЛЕН', icon="✅")
        else:
          st.warning('ШТРИХ КОД ПОДДЕЛАН', icon="⚠️")
            
    elif ('DRIVING' in front_text_list and 'LICENCE' in front_text_list) and front_obj_list[0] == 'Person':
        st.toast('ДОКУМЕНТ ОПРЕДЕЛЕН: ВОДИТЕЛЬСКИЕ ПРАВА', icon='✅')
        IINF, ID_DOCF = detec_date(front_text_list[1:])

    elif (front_obj_list[0] == '1D barcode') and ('СВИДЕТЕЛЬСТВО' and 'РОЖДЕНИИ' in front_text_list):
        st.toast('ДОКУМЕНТ ОПРЕДЕЛЕН: СВИДЕТЕЛЬСТВО O РОЖДЕНИИ', icon='✅')
        st.warning('ДОКУМЕНТ ЯВЛЯЕТСЯ БЕЗ СРОЧНЫМ', icon="⚠️")
    elif (front_obj_list[0] == '2D barcode') and ('АВТОРЛЫҚ' or 'АВТОРСКИМ' in front_text_list):
        st.toast('ДОКУМЕНТ ОПРЕДЕЛЕН: СВИДЕТЕЛЬСТВО О ПРАВЕ СОБСТВЕННОСТИ', icon='✅')
        st.warning('ДОКУМЕНТ ЯВЛЯЕТСЯ БЕЗ СРОЧНЫМ', icon="⚠️")
    else:
        st.toast('ДОКУМЕНТ НЕ ОПРЕДЕЛЕН!', icon='⚠️')

    if agree_getid:
        with st.spinner('Выполняется запрос на базу...'):
            loop = asyncio.new_event_loop()
            try:
                gov_f, gov_l, gov_m = loop.run_until_complete(getid(IINF))
                loop.close()
            except Exception as e:
                print('Не поличилось')
            if gov_f in front_text_list[1:] and gov_l in front_text_list[1:] and gov_m in front_text_list[1:]:
                st.success('ДАННЫЕ ПО ИИН СОВПАДАЕТ ПО ДОКУМЕНТАМ', icon="✅")
            else:
                st.warning('ДАННЫЕ ПО ИИН НЕ СОВПАДАЕТ ПО ДОКУМЕНТАМ', icon="⚠️")

    if 'ҚАЗАҚСТАН' in front_text_list or 'КАЗАКСТАН' in front_text_list:
        id_count = "Республики Казахстан."
        ico ='🇰🇿' 
    else:
        id_count = "Российской Федерации."
        ico = '🇷🇺'
    st.success(f'ДОКУМЕНТ ИЗ: {id_count}', icon=f"{ico}")

    edited_software = check_edit(front_file) or check_edit(back_file)
    if edited_software:
        st.error(f'Изображение было отредактировано с помощью: {edited_software}', icon="⚠️")
    else:
        st.success('В метаданных изображении не было найдено ошибок', icon="✅")
    print("agree_getid: ", agree_getid)


st.title("Распознавание документов и проверка подлинности")
st.text('''Основная задача системы состоит в проверке документа на подлинность. 
Тип / типы документов для проверки устанавливаются участниками самостоятельно. 
Какие именно документы проверяются.Например, паспорт гражданина определенной страны
водительские права, свидетельство о рождении, свидетельство о праве собственности 
и т.д. Система надежно выполняла проверку документов заранее установленного типа и 
сигнализировала о факте получения недействительного или просроченного документа.''')

col1, col2 = st.columns(2)

uploaded_files = st.file_uploader("Загрузите документы...", type=['png', 'jpeg', 'jpg'], accept_multiple_files=True)
if uploaded_files is not None:
    if len(uploaded_files) == 1:
        with col1:
            st.image(uploaded_files[0], width=300)
    elif len(uploaded_files) >= 2:
        with col1:
            st.image(uploaded_files[0], width=300)
        with col2:
            st.image(uploaded_files[1], width=300)

with st.popover("Поиск по ИИН"):
          Input_IIN = st.text_input("Ведите 12 значный ИИН:")
          if len(Input_IIN) == 12:
              with st.spinner('Выполняется запрос к базе данных....'):
                loop = asyncio.new_event_loop()
                try:
                    gov_f, gov_l, gov_m = loop.run_until_complete(getid(Input_IIN))
                    loop.close()
                except Exception as e:
                    Input_IIN = st.text_input("Введите 12 значный ИИН:", value='')
                    print('Не поличилось')
                loop.close()
                magic_str = {'ЖСН/ИИН': Input_IIN,
                             'Тегі/Фамилия': gov_f,
                             'Аты/Имя' :gov_l,
                             'Әкесінің аты/Отчество' : gov_m
                             }
                magican = True
                Input_IIN = st.text_input("Введите 12 значный ИИН:", value='')
agree_getid = st.checkbox('Проверка через базу')
if st.button("Выполнить", type="primary"):
        print('*' * 40, 'RUNNING PROGRAMM', '*' * 40)
        if uploaded_files[0] is not None and uploaded_files[1] is not None:
            print_detect = detect_and_print_info(uploaded_files[0], uploaded_files[1], agree_getid)
        else:
            st.error("Пожалуйста, загрузите обе части документа.")
if magican:
    for key, value in magic_str.items():
        st.header(f"{key} : {value}")