Функционал софта:
*** Создание базы данных, в которой хранятся имена акков, адреса, приватники, прокси, а также ведется учет проделанных активностей

*** Квази-рандомный выбор маршрута (определенную последовательность действий все равно приходится соблюдать)

*** Проверяет балансы эфира и стейблов в сетях Хеми и Сеполия, если недостаточно эфира в Хеми, то бриджит из Сеполии

*** Если недостаточно эфира в Сеполии и включен авторефилл в настройках, то сам будет пополнять из Оптимизма или Арбитрума, 
смотря где эфира больше И если его достаточно 
(больше чем верхняя граница авторефилла из настроек, поэтому не ставьте слишком много, 0.0005 хватит за глаза)

*** Стейблы минтятся с крана Ааве, строго по 10000 за транзу (обусловлено контрактом)
Логика та же, если нет стейблов в Хеми, то бриджим из Сеполии, если и в Сеполии их нет, то минтим

*** Когда везде всего хватает, выбирает рандомно между:
1) Созданием капсулы (лимит два раза в неделю). 
Стоит функция сброса состояния выполнения раз в три дня, соответственно если софт выключался или есть сомнения в выполнении этой активности, можно сбросить в меню состояния всех дейликов вручную выбрав функцию 4.

2) Свапом (лимит два раза в день)

3) Созданием сейфа (лимит один раз за все время)


Порядок действий:
1) Идем на сайт https://points.absinthe.network/hemi/d/connections
2) Коннектим кошелек и вводим реф код 147dc027 либо свой, подключаем твиттер
!!!ВНИМАНИЕ!!! 
без первых двух действий поинты кампании начисляться не будут

3) Открываем папку как проект в PyCharm (рекомендую, если на винде, хочется удобства и не жалко 4-5 гигов оперативки)
Либо открываем командную строку, пишем
cd {путь до вашей папки с софтом, можно скопипастить}
pip install -r requirements.txt
python app.py - запуск софта
3) Запускаем софт и выбираем вариант Exit
4) В папке с софтом создастся папка files, там редактируем settings.json, и вставляем данные в таблицу import.csv
private_key = 0x......
proxy = прокси в формате login:password@ip:port
name = забиваем любые имена, можно номера акков в таблице растянуть и заполнить
ОБЯЗАТЕЛЬНО!!! Зарегистрироваться на etherscan.io и вытащить оттуда свой апи ключ, это бесплатно
Данный апи ключ надо указать в настройках в соответствующем поле, а также вставить его в файл files/ETHERSCAN_API_KEY.txt, 
этот файл должен создаться автоматически при первом запуске вместе с остальными

5) Запускаем и выбираем вариант 1, создастся база данных, должно выдать Success
6) Запускаем и выбираем вариант 2, указываем желательное количество потоков 
(в режиме поддержания больше 3 не требуется, при первом запуске можно 10, но тогда будет тяжелее отслеживать ошибки) 
Скрипт работает!

7) Пункт меню 3 выдает из базы все кошельки которые получили отметку о недостаточном балансе.
Она ставится если кончился эфир в Сеполии и выключен авторефилл в настройках, либо если эфир кончился и в Арбитруме/Оптимизме
8) Пункт меню 4 сбрасывает все состояния активностей кроме сейфа вручную

Не забывайте периодически чистить логи, ибо со временем они могут раздуваться в размере
На работу софта не должно влиять, просто будут занимать место

Вы будете видеть достаточное количество ошибок, но это нормально, поскольку все происходит в тестнетах.
Если на протяжении нескольких десятков попыток отправить транзакцию не было ни одной успешной, тогда можете отписаться мне, запрошу у вас логи и посмотрю
Также при ручном стопе скрипта с огромной вероятностью вывалится полотно ошибок связанных с асинхронными задачами, это тоже нормально, просто забейте