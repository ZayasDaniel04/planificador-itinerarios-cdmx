import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

a = np.array([[1, 0, 1]])
b = np.array([[1, 1, 0]])
print("Todo funciona. Similitud:", cosine_similarity(a, b)[0][0])
