В данном репозитории реализовано базовое **API** для онлайн-магазина с помощью FastAPI  
Дергать "ручки" и оценивать работу эндпоинтов проще всего на странице http://127.0.0.1:8000/docs  
<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/f30d0f2c-22ef-4cb5-8286-57cdc406d234" />

**Как запустить сайт у себя?**  
python -m venv venv  
venv/Scripts/activate  
pip install -r ./requirements.txt  
uvicorn app.main:app --reload  

Доступна работа с:  
- продуктами  
- категориями продуктов  
- корзиной  
- заказами  
- пользователями в разных ролях (продавец, клиент, админ)  
Также реализована аутентификация и авторизация через JWT-токены  
