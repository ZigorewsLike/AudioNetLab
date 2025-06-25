import os

import onnxruntime as rt

from src.core.log_system import print_e, log_i, print_d


def load_sess_model(path: str, sess_provider: str = "DmlExecutionProvider") -> rt.InferenceSession:
    """
    Загрузка модели и создание сессии для предсказания

    :param path: Путь к onnx зашифрованной модели
    :param sess_provider: providers для загрузки модели (InferenceSession)
    :return: onnxruntime InferenceSession
    """
    print_d(f"Load model {os.path.basename(path)}: [{sess_provider}]")
    model_fstream = open(path, "rb")

    try:
        options = rt.SessionOptions()
        options.enable_mem_pattern = False
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        sess = rt.InferenceSession(model_fstream.read(), sess_options=options, providers=[sess_provider])
    except Exception as e:
        print_e(e)
        log_i('Переключение загрузки модели на CPU')
        sess = rt.InferenceSession(model_fstream.read(), providers=['CPUExecutionProvider'])
    model_fstream.close()

    return sess
