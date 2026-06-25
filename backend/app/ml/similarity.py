import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from sklearn.neighbors import NearestNeighbors
import joblib
from app.synthetic_ais import VESSEL_TYPE_MAP

class SimilaritySearch:
    def __init__(self, k=5):
        self.k = k
        self.scaler = MinMaxScaler()
        self.encoder = OneHotEncoder(sparse_output=False, handle_unknown='ignore')
        self.model = None
    
    def _fit_encoder_scaler(self, df):
        X_num = df[['risk_score', 'wind_speed', 'wave_height', 'season']].copy()
        self.scaler.fit(X_num)
        df['vessel_type_str'] = df['vessel_type'].apply(
            lambda x: VESSEL_TYPE_MAP.get(x, "other")
        )
        self.encoder.fit(df[['vessel_type_str']])
        return df
    
    def _transform_features(self, df):
        X_num = df[['risk_score', 'wind_speed', 'wave_height', 'season']].copy()
        X_num_scaled = self.scaler.transform(X_num)
        vessel_encoded = self.encoder.transform(df[['vessel_type_str']])
        return np.hstack([X_num_scaled, vessel_encoded])
    
    def fit(self, df):
        df = self._fit_encoder_scaler(df)
        features = self._transform_features(df)
        self.model = NearestNeighbors(n_neighbors=self.k, metric='euclidean')
        self.model.fit(features)
        return self
    
    def predict(self, query, df_reference=None):
        q_df = pd.DataFrame([query])
        q_df['vessel_type_str'] = q_df['vessel_type'].apply(
            lambda x: x if isinstance(x, str) else "other"
        )
        X_num_q = q_df[['risk_score', 'wind_speed', 'wave_height', 'season']].copy()
        X_num_q_scaled = self.scaler.transform(X_num_q)
        vessel_encoded_q = self.encoder.transform(q_df[['vessel_type_str']])
        features_q = np.hstack([X_num_q_scaled, vessel_encoded_q])
        distances, indices = self.model.kneighbors(features_q)
        if df_reference is not None:
            neighbor_risks = df_reference.iloc[indices[0]]['risk_score'].values
            best_idx = np.argmin(neighbor_risks)
            recommended_index = indices[0][best_idx]
            return indices[0], distances[0], recommended_index
        else:
            return indices[0], distances[0], None
    
    def save(self, path="models/knn_model.joblib"):
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'encoder': self.encoder,
            'k': self.k
        }, path)
    
    def load(self, path="models/knn_model.joblib"):
        data = joblib.load(path)
        self.model = data['model']
        self.scaler = data['scaler']
        self.encoder = data['encoder']
        self.k = data['k']
