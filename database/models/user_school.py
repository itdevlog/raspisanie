from datetime import datetime
from typing import Dict, List, Optional
from config.schools import DEFAULT_SCHOOL_ID

class UserSchool:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.selected_schools: List[str] = [DEFAULT_SCHOOL_ID]
        self.current_school: str = DEFAULT_SCHOOL_ID
        self.school_preferences: Dict[str, Dict] = {}
        self.created_at: datetime = datetime.now()
        self.updated_at: datetime = datetime.now()
    
    def add_school(self, school_id: str) -> bool:
        if school_id not in self.selected_schools:
            self.selected_schools.append(school_id)
            self.updated_at = datetime.now()
            return True
        return False
    
    def remove_school(self, school_id: str) -> bool:
        if school_id in self.selected_schools:
            self.selected_schools.remove(school_id)
            
            # Если удаляем текущую школу, переключаем на первую доступную
            if self.current_school == school_id and self.selected_schools:
                self.current_school = self.selected_schools[0]
            
            self.updated_at = datetime.now()
            return True
        return False
    
    def switch_school(self, school_id: str) -> bool:
        if school_id in self.selected_schools:
            self.current_school = school_id
            self.updated_at = datetime.now()
            return True
        return False
    
    def get_school_preferences(self, school_id: str) -> Dict:
        return self.school_preferences.get(school_id, {})
    
    def set_school_preferences(self, school_id: str, preferences: Dict) -> None:
        if school_id not in self.school_preferences:
            self.school_preferences[school_id] = {}
        
        self.school_preferences[school_id].update(preferences)
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            'user_id': self.user_id,
            'selected_schools': self.selected_schools,
            'current_school': self.current_school,
            'school_preferences': self.school_preferences,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSchool':
        user_school = cls(data['user_id'])
        user_school.selected_schools = data['selected_schools']
        user_school.current_school = data['current_school']
        user_school.school_preferences = data['school_preferences']
        user_school.created_at = datetime.fromisoformat(data['created_at'])
        user_school.updated_at = datetime.fromisoformat(data['updated_at'])
        return user_school