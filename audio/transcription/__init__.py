"""Speaker-attributed transcription: language-routed faster-whisper + pyannote diarization.

See pipeline.py (entry point), transcribe.py (ASR + routing), diarize.py (speakers).
"""
import ctypes
import glob
import os
import sys


def _preload_env_cudnn():
    """Load the env's pip cuDNN sub-libraries before torch/ctranslate2 touch cuDNN.

    Otherwise the core libcudnn (9.1, from the env) dlopens its sub-libraries (libcudnn_ops, _cnn, ...) by
    soname and finds the system-wide /usr/lib/x86_64-linux-gnu copies (9.8): torch's RNN then fails with
    CUDNN_STATUS_SUBLIBRARY_VERSION_MISMATCH once faster-whisper and pyannote share a process.
    """
    for site in sys.path:
        lib_dir = os.path.join(site, "nvidia", "cudnn", "lib")
        if os.path.isdir(lib_dir):
            libs = glob.glob(os.path.join(lib_dir, "libcudnn*.so.*"))
            # core first, then the sub-libraries it would otherwise resolve from the system
            for path in sorted(libs, key=lambda p: os.path.basename(p) != "libcudnn.so.9"):
                try:
                    ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                except OSError:
                    pass
            return


_preload_env_cudnn()
