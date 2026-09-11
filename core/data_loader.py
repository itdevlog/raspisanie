import requests
import re
import json
import time
import logging
from typing import Optional, Dict
from config.schools import SCHOOLS_CONFIG  # Добавить импорт

class DataLoader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = logging.getLogger(__name__)

    def get_current_filename(self, check_url: str, max_retries: int = 3) -> Optional[str]:
        """Получает актуальное имя файла из check страницы с повторными попытками"""
        for attempt in range(max_retries):
            try:
                response = self.session.get(check_url, timeout=10)
                response.raise_for_status()
                
                # Простой поиск имени файла
                pattern = r'(\d+_\d+\.js)'
                match = re.search(pattern, response.text)
                
                if match:
                    return match.group(1)
                
                # Альтернативный поиск в <pre> теге
                pre_match = re.search(r'<pre[^>]*>(.*?)</pre>', response.text, re.DOTALL)
                if pre_match:
                    pre_content = pre_match.group(1).strip()
                    file_match = re.search(pattern, pre_content)
                    if file_match:
                        return file_match.group(1)
                
                return None
                    
            except Exception as e:
                print(f"⚠️ Попытка {attempt + 1} не удалась для {check_url}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
    
    def download_schedule_data(self, base_url: str, filename: str, max_retries: int = 3) -> Optional[Dict]:
        """Скачивает и парсит данные расписания с повторными попытками"""
        for attempt in range(max_retries):
            try:
                url = f"{base_url}{filename}"
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                js_content = response.text
                
                # Парсим JavaScript файл с var NIKA = {...}
                if 'var NIKA=' in js_content:
                    json_str = js_content.split('var NIKA=', 1)[1].strip()
                    
                    # Убираем возможную точку с запятой в конце
                    if json_str.endswith(';'):
                        json_str = json_str[:-1]
                    
                    data = json.loads(json_str)
                    return data
                else:
                    return None
                    
            except Exception as e:
                print(f"⚠️ Попытка {attempt + 1} не удалась для {filename}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
    
    def load_school_data(self, school_config: Dict, max_retries: int = 3) -> Optional[Dict]:
        """Полная загрузка данных для школы с повторными попытками"""
        school_name = school_config['name']
        
        for attempt in range(max_retries):
            self.logger.info(f"Попытка {attempt + 1} загрузки данных для {school_name}...")
            
            filename = self.get_current_filename(school_config['check_url'])
            if not filename:
                self.logger.warning(f"Не удалось получить имя файла для {school_name}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
            
            data = self.download_schedule_data(school_config['base_url'], filename)
            if data:
                self.logger.info(f"Данные для {school_name} успешно загружены")
                return data
            else:
                self.logger.warning(f"Не удалось загрузить данные для {school_name}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return None
    
    def load_all_schools_data(self) -> Dict[str, Dict]:
        """Загружает данные для всех активных школ"""
        schools_data = {}
        failed_schools = []
        
        for school_id, school_config in SCHOOLS_CONFIG.items():
            if school_config.get('active', True):
                print(f"🔄 Загрузка данных для {school_config['name']}...")
                school_data = self.load_school_data(school_config)
                if school_data:
                    schools_data[school_id] = school_data
                    print(f"✅ Данные для {school_config['name']} загружены")
                else:
                    print(f"❌ Не удалось загрузить данные для {school_config['name']}")
                    failed_schools.append(school_config['name'])
        
        if failed_schools:
            print(f"\n⚠️ Не удалось загрузить данные для {len(failed_schools)} школ:")
            for school_name in failed_schools:
                print(f"   ❌ {school_name}")
        
        return schools_data