import os

import onnxruntime as rt

from src.core.log_system import print_e, log_i, print_d


def load_sess_model(path: str, sess_provider: str = "DmlExecutionProvider") -> rt.InferenceSession:
    """Load an ONNX model and create an inference session.

    :param path: Path to the onnx file.
    :param sess_provider: Execution provider, for example DmlExecutionProvider or CPUExecutionProvider.
    :returns: onnxruntime InferenceSession, falls back to CPU when the provider is unavailable.
    """
    print_d(f"Load model {os.path.basename(path)}: [{sess_provider}]")
    with open(path, "rb") as model_fstream:
        model_bytes = model_fstream.read()  # Read once, the CPU fallback needs the same bytes

    try:
        options = rt.SessionOptions()
        options.enable_mem_pattern = False
        options.execution_mode = rt.ExecutionMode.ORT_SEQUENTIAL
        sess = rt.InferenceSession(model_bytes, sess_options=options, providers=[sess_provider])
    except Exception as e:
        print_e(e)
        log_i('Falling back to CPU model loading')
        sess = rt.InferenceSession(model_bytes, providers=['CPUExecutionProvider'])

    return sess