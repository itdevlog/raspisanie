from datetime import datetime

from config.schools import DEFAULT_SCHOOL_ID


class UserService:
    def __init__(self, db):
        self.db = db
        self.users_collection = db.get_collection('users')

    def get_user_school(self, user_id: int) -> str:
        """Получает выбранную школу пользователя"""
        user = self.users_collection.find_one({'user_id': user_id})
        if user and 'current_school' in user:
            return user['current_school']
        return DEFAULT_SCHOOL_ID

    def set_user_school(self, user_id: int, school_id: str) -> bool:
        """Устанавливает школу для пользователя, сохраняя остальные поля.

        Обновляем существующий документ (find → copy → точечные поля), а не собираем
        его заново: так код не зависит от того, мержит ли бэкенд поля при update_one,
        и любые будущие поля пользователя гарантированно сохраняются.
        """
        from config.schools import SCHOOLS_CONFIG
        school = SCHOOLS_CONFIG.get(school_id)
        if not school or not school.get('active', True):
            return False

        user = self.users_collection.find_one({'user_id': user_id})
        if user:
            user_data = user.copy()
        else:
            user_data = {
                'user_id': user_id,
                'school_classes': {},
                'created_at': datetime.now().isoformat(),
            }

        user_data['current_school'] = school_id
        user_data['updated_at'] = datetime.now().isoformat()

        self.users_collection.update_one(
            {'user_id': user_id},
            user_data,
            upsert=True
        )
        return True

    def get_user_class(self, user_id: int, school_id: str = None) -> str | None:
        """Получает выбранный класс пользователя для конкретной школы"""
        user = self.users_collection.find_one({'user_id': user_id})
        if not user:
            return None

        # Если school_id не указан, используем текущую школу пользователя
        if school_id is None:
            school_id = user.get('current_school', DEFAULT_SCHOOL_ID)

        # Получаем класс для указанной школы
        school_classes = user.get('school_classes', {})
        return school_classes.get(school_id)

    def set_user_class(self, user_id: int, class_name: str, school_id: str = None) -> bool:
        """Устанавливает класс для пользователя для конкретной школы"""
        user = self.users_collection.find_one({'user_id': user_id})

        # Если school_id не указан, используем текущую школу пользователя
        if school_id is None:
            if user and 'current_school' in user:
                school_id = user['current_school']
            else:
                school_id = DEFAULT_SCHOOL_ID

        # Получаем текущие данные или создаем новые
        if user:
            user_data = user.copy()
        else:
            user_data = {
                'user_id': user_id,
                'current_school': school_id,
                'school_classes': {},
                'created_at': datetime.now().isoformat()
            }

        # Инициализируем school_classes если нет
        if 'school_classes' not in user_data:
            user_data['school_classes'] = {}

        # Устанавливаем класс для школы
        user_data['school_classes'][school_id] = class_name
        user_data['updated_at'] = datetime.now().isoformat()

        self.users_collection.update_one(
            {'user_id': user_id},
            user_data,
            upsert=True
        )
        return True

    def set_user_notification_settings(self, user_id: int, notifications_enabled: bool, school_id: str = None) -> bool:
        """Устанавливает настройки уведомлений для пользователя для конкретной школы"""
        user = self.users_collection.find_one({'user_id': user_id})

        # Если school_id не указан, используем текущую школу пользователя
        if school_id is None:
            if user and 'current_school' in user:
                school_id = user['current_school']
            else:
                school_id = DEFAULT_SCHOOL_ID

        # Получаем текущие данные или создаем новые
        if user:
            user_data = user.copy()
        else:
            user_data = {
                'user_id': user_id,
                'current_school': school_id,
                'school_classes': {},
                'notification_settings': {},
                'created_at': datetime.now().isoformat()
            }

        # Инициализируем notification_settings если нет
        if 'notification_settings' not in user_data:
            user_data['notification_settings'] = {}

        # Устанавливаем настройки уведомлений для школы
        user_data['notification_settings'][school_id] = notifications_enabled
        user_data['updated_at'] = datetime.now().isoformat()

        self.users_collection.update_one(
            {'user_id': user_id},
            user_data,
            upsert=True
        )
        return True

    def get_user_notification_settings(self, user_id: int, school_id: str = None) -> bool:
        """Получает настройки уведомлений пользователя для конкретной школы"""
        user = self.users_collection.find_one({'user_id': user_id})
        if not user:
            return True  # По умолчанию уведомления включены

        # Если school_id не указан, используем текущую школу пользователя
        if school_id is None:
            school_id = user.get('current_school', DEFAULT_SCHOOL_ID)

        # Получаем настройки уведомлений для указанной школы
        notification_settings = user.get('notification_settings', {})
        return notification_settings.get(school_id, True)  # По умолчанию включены

    def clear_user_class(self, user_id: int, school_id: str = None) -> bool:
        """Очищает выбранный класс пользователя для конкретной школы"""
        user = self.users_collection.find_one({'user_id': user_id})
        if not user:
            return False

        # Если school_id не указан, используем текущую школу пользователя
        if school_id is None:
            school_id = user.get('current_school', DEFAULT_SCHOOL_ID)

        # Создаем копию данных пользователя
        user_data = user.copy()

        # Удаляем класс для указанной школы
        if 'school_classes' in user_data and school_id in user_data['school_classes']:
            del user_data['school_classes'][school_id]
            user_data['updated_at'] = datetime.now().isoformat()

            self.users_collection.update_one(
                {'user_id': user_id},
                user_data
            )
            return True

        return False

    def get_current_class(self, user_id: int) -> str | None:
        """Получает класс для текущей школы пользователя"""
        current_school_id = self.get_user_school(user_id)
        return self.get_user_class(user_id, current_school_id)

    def get_user_data(self, user_id: int) -> dict:
        """Получает все данные пользователя"""
        user = self.users_collection.find_one({'user_id': user_id})
        if not user:
            return {
                'user_id': user_id,
                'current_school': DEFAULT_SCHOOL_ID,
                'school_classes': {},
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
        return user

    def get_users_with_classes(self) -> list:
        """Получает всех пользователей, у которых выбран класс"""
        all_users = self.users_collection.find({})
        users_with_classes = []

        for user in all_users:
            # Проверяем, есть ли у пользователя хотя бы один класс в school_classes
            if user.get('school_classes'):
                users_with_classes.append(user)

        return users_with_classes
