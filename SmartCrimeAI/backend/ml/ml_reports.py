"""
ml_reports.py — Training report generator with charts.
Generates confusion matrix, ROC curve, precision-recall curve, feature importance, and model comparisons.
"""

import os
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, roc_curve, precision_recall_curve, auc

class ReportGenerator:
    """Generates charts and reports from model evaluation metrics."""

    @staticmethod
    def _setup_theme():
        """Setup clean, modern styling for matplotlib charts."""
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        # Custom parameters for high premium design
        matplotlib.rcParams['figure.facecolor'] = '#121214'
        matplotlib.rcParams['axes.facecolor'] = '#1a1a1e'
        matplotlib.rcParams['axes.edgecolor'] = '#2c2c35'
        matplotlib.rcParams['axes.labelcolor'] = '#e4e4e7'
        matplotlib.rcParams['text.color'] = '#e4e4e7'
        matplotlib.rcParams['xtick.color'] = '#a1a1aa'
        matplotlib.rcParams['ytick.color'] = '#a1a1aa'
        matplotlib.rcParams['grid.color'] = '#2c2c35'
        matplotlib.rcParams['font.size'] = 10
        matplotlib.rcParams['font.family'] = 'sans-serif'

    @classmethod
    def generate_confusion_matrix(cls, y_test, y_pred, dataset_size, output_dir="output/reports"):
        """Generates and saves a modern confusion matrix heatmap."""
        os.makedirs(output_dir, exist_ok=True)
        cls._setup_theme()

        cm = confusion_matrix(y_test, y_pred)
        
        fig, ax = plt.subplots(figsize=(6, 5))
        
        # Draw heatmap manually or using matshow for maximum styling control
        im = ax.imshow(cm, cmap='Blues', interpolation='nearest')
        
        # Colorbar with styled ticks
        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.yaxis.set_tick_params(color='#a1a1aa')
        cbar.outline.set_edgecolor('#2c2c35')
        
        # Labels and ticks
        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(['No Crime', 'Crime'], fontsize=10)
        ax.set_yticklabels(['No Crime', 'Crime'], fontsize=10)
        ax.set_xlabel('Predicted Label', fontweight='bold', labelpad=10)
        ax.set_ylabel('True Label', fontweight='bold', labelpad=10)
        ax.set_title(f'Confusion Matrix (Database: {dataset_size} rows)', fontsize=12, fontweight='bold', pad=15)
        
        # Write text values inside cells
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                ax.text(j, i, format(cm[i, j], 'd'),
                        ha="center", va="center",
                        color="white" if cm[i, j] > thresh else "#e4e4e7",
                        fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        path = os.path.join(output_dir, f'confusion_matrix_{dataset_size}.png')
        plt.savefig(path, dpi=300, facecolor='#121214')
        plt.close()
        return path

    @classmethod
    def generate_roc_curve(cls, y_test, y_proba, dataset_size, output_dir="output/reports"):
        """Generates and saves a styled ROC curve with AUC annotation."""
        os.makedirs(output_dir, exist_ok=True)
        cls._setup_theme()

        fpr, tpr, _ = roc_curve(y_test, y_proba)
        roc_auc = auc(fpr, tpr)

        fig, ax = plt.subplots(figsize=(7, 5.5))
        ax.plot(fpr, tpr, color='#3b82f6', lw=2.5, label=f'ROC Curve (AUC = {roc_auc:.3f})')
        ax.plot([0, 1], [0, 1], color='#ef4444', lw=1.5, linestyle='--', label='Random Guess')
        
        ax.set_xlim([-0.02, 1.02])
        ax.set_ylim([-0.02, 1.02])
        ax.set_xlabel('False Positive Rate', fontweight='bold', labelpad=10)
        ax.set_ylabel('True Positive Rate', fontweight='bold', labelpad=10)
        ax.set_title(f'Receiver Operating Characteristic (Database: {dataset_size} rows)', fontsize=12, fontweight='bold', pad=15)
        ax.legend(loc="lower right", frameon=True, facecolor='#1a1a1e', edgecolor='#2c2c35')
        
        plt.tight_layout()
        path = os.path.join(output_dir, f'roc_curve_{dataset_size}.png')
        plt.savefig(path, dpi=300, facecolor='#121214')
        plt.close()
        return path

    @classmethod
    def generate_pr_curve(cls, y_test, y_proba, dataset_size, output_dir="output/reports"):
        """Generates and saves a styled Precision-Recall curve."""
        os.makedirs(output_dir, exist_ok=True)
        cls._setup_theme()

        precision, recall, _ = precision_recall_curve(y_test, y_proba)
        pr_auc = auc(recall, precision)

        fig, ax = plt.subplots(figsize=(7, 5.5))
        ax.plot(recall, precision, color='#10b981', lw=2.5, label=f'PR Curve (AUC = {pr_auc:.3f})')
        
        ax.set_xlim([-0.02, 1.02])
        ax.set_ylim([-0.02, 1.02])
        ax.set_xlabel('Recall', fontweight='bold', labelpad=10)
        ax.set_ylabel('Precision', fontweight='bold', labelpad=10)
        ax.set_title(f'Precision-Recall Curve (Database: {dataset_size} rows)', fontsize=12, fontweight='bold', pad=15)
        ax.legend(loc="lower left", frameon=True, facecolor='#1a1a1e', edgecolor='#2c2c35')
        
        plt.tight_layout()
        path = os.path.join(output_dir, f'pr_curve_{dataset_size}.png')
        plt.savefig(path, dpi=300, facecolor='#121214')
        plt.close()
        return path

    @classmethod
    def generate_feature_importance(cls, feature_names, importances, dataset_size, output_dir="output/reports"):
        """Generates and saves a feature importance horizontal bar chart."""
        os.makedirs(output_dir, exist_ok=True)
        cls._setup_theme()

        # Sort feature importances in descending order
        indices = np.argsort(importances)
        
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Color gradient for bars (sleek purple to blue)
        colors = plt.cm.plasma(np.linspace(0.4, 0.8, len(indices)))
        
        bars = ax.barh(range(len(indices)), importances[indices], color=colors, edgecolor='#2c2c35', height=0.6)
        
        ax.set_yticks(range(len(indices)))
        ax.set_yticklabels([feature_names[i] for i in indices], fontweight='bold')
        ax.set_xlabel('Relative Importance', fontweight='bold', labelpad=10)
        ax.set_title(f'Random Forest Feature Importance (Database: {dataset_size} rows)', fontsize=12, fontweight='bold', pad=15)
        
        # Annotate actual values on the bars
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.005, bar.get_y() + bar.get_height()/2, f'{width:.3f}', 
                    va='center', ha='left', fontsize=9, color='#a1a1aa')
            
        ax.set_xlim([0, max(importances) * 1.15])
        
        plt.tight_layout()
        path = os.path.join(output_dir, f'feature_importance_{dataset_size}.png')
        plt.savefig(path, dpi=300, facecolor='#121214')
        plt.close()
        return path

    @classmethod
    def generate_model_comparison(cls, rf_metrics, gnn_metrics, dataset_size, output_dir="output/reports"):
        """Generates and saves a model comparison bar chart between RF and GNN."""
        os.makedirs(output_dir, exist_ok=True)
        cls._setup_theme()

        metrics = ['precision', 'recall', 'f1', 'roc_auc']
        rf_vals = [rf_metrics.get(m, 0.0) for m in metrics]
        gnn_vals = [gnn_metrics.get(m, 0.0) for m in metrics]
        
        x = np.arange(len(metrics))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(8, 5.5))
        rects1 = ax.bar(x - width/2, rf_vals, width, label='Random Forest (Tabular)', color='#3b82f6', edgecolor='#2c2c35')
        rects2 = ax.bar(x + width/2, gnn_vals, width, label='Graph Neural Network (Spatio-Temporal)', color='#8b5cf6', edgecolor='#2c2c35')
        
        ax.set_ylabel('Scores', fontweight='bold', labelpad=10)
        ax.set_title(f'Model Comparison: RF vs GNN (Database: {dataset_size} rows)', fontsize=12, fontweight='bold', pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels([m.upper().replace('_', ' ') for m in metrics], fontweight='bold')
        ax.set_ylim([0, 1.15])
        ax.legend(loc="upper right", frameon=True, facecolor='#1a1a1e', edgecolor='#2c2c35')
        
        # Add value labels on top of the bars
        def autolabel(rects):
            for rect in rects:
                height = rect.get_height()
                ax.annotate(f'{height:.2f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom', fontsize=9)

        autolabel(rects1)
        autolabel(rects2)
        
        plt.tight_layout()
        path = os.path.join(output_dir, f'model_comparison_{dataset_size}.png')
        plt.savefig(path, dpi=300, facecolor='#121214')
        plt.close()
        return path

    @classmethod
    def append_training_history(cls, tick, dataset_size, rf_metrics, gnn_metrics, output_dir="output"):
        """Appends retrain performance to training_history.json and latest_report.json."""
        os.makedirs(output_dir, exist_ok=True)
        history_path = os.path.join(output_dir, 'training_history.json')
        latest_path = os.path.join(output_dir, 'latest_report.json')
        
        record = {
            "tick": int(tick),
            "dataset_size": int(dataset_size),
            "rf_metrics": rf_metrics,
            "gnn_metrics": gnn_metrics
        }
        
        # Load existing history
        history = []
        if os.path.isfile(history_path):
            try:
                with open(history_path, 'r') as f:
                    history = json.load(f)
            except Exception:
                history = []
                
        history.append(record)
        
        # Save history
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=2)
            
        # Save latest report
        latest_report = {
            **record,
            "charts": {
                "confusion_matrix": f"/reports/confusion_matrix_{dataset_size}.png",
                "roc_curve": f"/reports/roc_curve_{dataset_size}.png",
                "pr_curve": f"/reports/pr_curve_{dataset_size}.png",
                "feature_importance": f"/reports/feature_importance_{dataset_size}.png",
                "model_comparison": f"/reports/model_comparison_{dataset_size}.png"
            }
        }
        with open(latest_path, 'w') as f:
            json.dump(latest_report, f, indent=2)
            
        print(f"[ReportGenerator] Saved training history and latest report for dataset size {dataset_size}.")

    @classmethod
    def generate_full_report(cls, trainer, gnn_trainer, X_test, y_test, tick, dataset_size):
        """Generates all charts, comparisons, and history updates in one call."""
        try:
            print(f"[ReportGenerator] Starting full report generation for database size {dataset_size}...")
            
            # Predict probabilities and classes
            y_pred_rf = trainer.classifier.predict(X_test)
            y_proba_rf = trainer.classifier.predict_proba(X_test)[:, 1]
            
            # Generate primary RF plots
            cls.generate_confusion_matrix(y_test, y_pred_rf, dataset_size)
            cls.generate_roc_curve(y_test, y_proba_rf, dataset_size)
            cls.generate_pr_curve(y_test, y_proba_rf, dataset_size)
            
            # Feature importance
            feature_names = list(X_test.columns)
            importances = trainer.classifier.feature_importances_
            cls.generate_feature_importance(feature_names, importances, dataset_size)
            
            # GNN metrics
            gnn_metrics = {}
            if gnn_trainer and gnn_trainer.is_trained:
                gnn_metrics = gnn_trainer.eval_metrics
                # Generate comparison plot
                cls.generate_model_comparison(trainer.eval_metrics, gnn_metrics, dataset_size)
            else:
                # If no GNN, compare GNN as zero metrics
                gnn_metrics = {"precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0}
                cls.generate_model_comparison(trainer.eval_metrics, gnn_metrics, dataset_size)
                
            # Append history
            cls.append_training_history(tick, dataset_size, trainer.eval_metrics, gnn_metrics)
            print("[ReportGenerator] Successfully generated all charts and report metrics!")
            
        except Exception as e:
            print(f"[ReportGenerator] Error generating full report: {e}")
            import traceback
            traceback.print_exc()
