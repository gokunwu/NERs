import os
from config import *
from model import *
from util import *
import pandas as pd
import pickle
from collections import defaultdict
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import precision_recall_fscore_support, confusion_matrix, precision_score, recall_score, f1_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def pre_recall_f1_sup(y_true, y_pred, labels, fname):
    mat = precision_recall_fscore_support(y_true, y_pred, labels=labels)
    mat = {"Precision": mat[0], "Recall": mat[1], "F1-Score": mat[2], "Support": mat[3]}
    df = pd.DataFrame(mat, index=labels)
    df = df[df.Support > 0]

    avg_p = precision_score(y_true, y_pred, average='weighted')
    avg_r = recall_score(y_true, y_pred, average='weighted')
    avg_f1 = f1_score(y_true, y_pred, average='weighted')
    all_support = df.Support.sum()
    df.loc['Mean/Total'] = [avg_p, avg_r, avg_f1, all_support]
    df = df.round(decimals=4)
    df[["Support"]] = df[["Support"]].astype(int)
    df.to_csv(fname)
    return df


def confu_matrix(y_true, pred_tags, labels, fname):
    cm = confusion_matrix(y_true, pred_tags, labels=labels)
    data = pd.DataFrame(cm, columns=labels, index=labels)
    f, ax = plt.subplots(figsize=(18, 15))
    sns.heatmap(data, annot=True, fmt="d", cmap="YlGnBu")
    ax.set_title(f"{fname.split('_')[0]} Confusion Matrix", fontsize=24)
    ax.set_xlabel("Predict Labels", fontsize=12)
    ax.set_ylabel("True Labels", fontsize=12)
    plt.savefig(fname, dpi=300)


def evaluate(datas, tagger, device, tag_to_ix):
    taggername = type(tagger).__name__
    logger.info(f"***** Evaluating {taggername} *****")
    ix_to_tag = {v: k for k, v in tag_to_ix.items()}
    input_ids = datas[:, :, 0].to(device)
    tag_ids = datas[:, :, 1].to(device)
    tags = []
    pred_tags = []
    for idx in range(tag_ids.shape[0]):
        pred = tagger.predict_one(input_ids[idx])
        for i in range(tag_ids.shape[1]):
            if tag_ids[idx, i] == tag_to_ix['[PAD]']:
                break
            tags.append(ix_to_tag[tag_ids[idx][i].item()])
            pred_tags.append(ix_to_tag[pred[i].item()])

    labels = list(tag_to_ix.keys())
    prfsname = os.path.join(EVAL_LOG_DIR, f"{taggername}_prfs.csv")
    cnfumatname = os.path.join(EVAL_LOG_DIR, f"{taggername}_confu_mat.png")

    df = pre_recall_f1_sup(tags, pred_tags, labels, prfsname)
    confu_matrix(tags, pred_tags, labels, cnfumatname)
    
    return df.loc['Mean/Total'][:-1]


def main():
    logger.info(f"***** Loading Eval Data *****")
    test_data = load_data(TEST_FILE_NAME)
    word_to_ix, tag_to_ix = load_dict()

    logger.info(f"***** Generating Testing Data *****")
    test_dataset = convert_tokens_to_ids(test_data, MAX_LEN, word_to_ix, tag_to_ix)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info(f"***** Initializing Model *****")
    params = [len(word_to_ix), WORD_EMBEDDING_DIM, HIDDEN_DIM, len(tag_to_ix)]
    taggers = [
        LRTagger(*params[:2], len(tag_to_ix), device=device),
        HMMTagger(len(word_to_ix), len(tag_to_ix)),
        CNNTagger(*params, device=device),
        BiLSTMTagger(*params, device=device),
        BiLSTMAttTagger(*params, word_to_ix['[PAD]'], device=device),
        BiLSTMCNNTagger(*params, device=device),
        CNNBiLSTMTagger(*params, device=device),
        CNNBiLSTMAttTagger(*params, word_to_ix['[PAD]'], device=device)
    ]

    results = pd.DataFrame(columns=['Precision', 'Recall', 'F1-Score'])
    for tagger in taggers:
        taggername = type(tagger).__name__

        logger.info(f"***** Loading {taggername} *****")
        tagger.load(os.path.join(OUTPUT_DIR, f'{taggername}_model.pt'))

        logger.info(f"***** Evaling {taggername} *****")
        score = evaluate(test_dataset, tagger, device, tag_to_ix)
        results.loc[taggername] = score
    print(results)
    results.to_csv(os.path.join(EVAL_LOG_DIR, 'total_results.csv'))


if __name__ == "__main__":
    main()