from datetime import datetime


def fim_de_semana(data_texto):

    data = datetime.strptime(
        data_texto,
        "%Y-%m-%d"
    )

    return data.weekday() >= 5