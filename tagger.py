import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from model import *
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TorchTagger(object):
    def __init__(self, model, lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        self.model = model
        self.batch_size = batch_size
        self.epochs = epochs
        self.loss_fct = nn.CrossEntropyLoss(ignore_index=ignore_index)
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        self.device = device
        self.print_step = print_step

    def create_input_dataset(self, X, y):
        return TensorDataset(X, y)

    def fit(self, X, y):
        self.model.to(self.device)
        self.model.train()

        train_dataset = self.create_input_dataset(X, y)
        train_dataloader = DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True)

        for epoch in range(self.epochs):
            logger.info(f"***** Epoch {epoch} *****")
            for step, batch in enumerate(train_dataloader):
                self.optimizer.zero_grad()
                batch = tuple(t.to(self.device) for t in batch)
                tag_ids = batch[-1]
                logits = self.model(*batch[:-1])
                loss = self.loss_fct(
                    logits.view(-1, self.model.tag_dim), tag_ids.view(-1))
                loss.backward()
                self.optimizer.step()
                if step % self.print_step == 0:
                    logger.info(
                        f"[epoch]: {epoch}, [batch]: {step}, [loss]: {loss.item()}")

    def score(self, X, softmax=False):
        self.model.to(self.device)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(X)
        return F.softmax(logits, dim=-1) if softmax else logits

    def predict(self, X):
        scores = self.score(X)
        return scores.argmax(dim=-1)

    def predict_one(self, X):
        X = X.unsqueeze(0)
        return self.predict(X).squeeze()

    def save(self, filename):
        torch.save(self.model.state_dict(), filename)

    def load(self, filename):
        self.model.load_state_dict(torch.load(filename))


class TorchAttTagger(TorchTagger):
    def __init__(self, model, lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, pad_index=0, print_step=5):
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)
        self.pad_index = pad_index

    def creat_attention_mask(self, X):
        """
        if sent = [I have a dream], max_len = 8, then
        mask = [1 1 1 1 0 0 0 0]

        :param X: shape=[len, max_len]
        :return:
        """
        att_mask = torch.ones(X.shape)
        att_mask[X == self.pad_index] = 0
        return att_mask

    def create_input_dataset(self, X, y):
        input_mask = self.creat_attention_mask(X)
        return TensorDataset(X, input_mask, y)

    def score(self, X, softmax=False):
        self.model.to(self.device)
        self.model.eval()
        att_mask = self.creat_attention_mask(X).to(self.device)
        with torch.no_grad():
            logits = self.model(X, att_mask)
        return F.softmax(logits, dim=-1) if softmax else logits


class LRTagger(TorchTagger):
    def __init__(self, vocab_size, embed_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        model = LogisticRegression(vocab_size, embed_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)


class BiLSTMTagger(TorchTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        model = BiLSTM(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)


class BiLSTMAttTagger(TorchAttTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, pad_index=0, print_step=5):
        model = BiLSTMAtt(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, pad_index, print_step)


class CNNTagger(TorchTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        model = CNN(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)


class BiLSTMCNNTagger(TorchTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        model = BiLSTMCNN(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)


class CNNBiLSTMAttTagger(TorchAttTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, pad_index=0, print_step=5):
        model = CNNBiLSTMAtt(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, pad_index, print_step)


class CNNBiLSTMTagger(TorchTagger):
    def __init__(self, vocab_size, embed_dim, hidden_dim, tag_dim,
                 lr=0.01, batch_size=32, epochs=5, device='cpu', ignore_index=0, print_step=5):
        model = CNNBiLSTM(vocab_size, embed_dim, hidden_dim, tag_dim)
        super().__init__(model, lr, batch_size, epochs, device, ignore_index, print_step)


class HMMTagger(object):
    """
    Hidden Markov Model Tagger.
    """

    def __init__(self, n_ob, n_status, tag_pad_ix=0, eps=1e-6):
        # Initial state probability matrix.
        self.pi = torch.zeros(n_status)
        # State transition probability matrix.
        self.trans = torch.zeros(n_status, n_status)
        # Observation state transition probability matrix.
        self.obprob = torch.zeros(n_status, n_ob)
        self.tag_pad_ix = tag_pad_ix # Padding ID
        self.eps = eps # A very small number.

    def fit(self, X, y):
        """
        :param X: shape=[batch_size, max_len]
        :param y: shape=[batch_size, max_len]
        :return: None
        """
        for first in y[0, :]:
            self.pi[first] += 1
        self.pi[self.pi == 0.] = self.eps
        self.pi /= self.pi.sum()

        for i in range(y.shape[0]):
            for j in range(y.shape[1]):
                self.obprob[y[i, j], X[i, j]] += 1
                if y[i, j + 1] == self.tag_pad_ix:
                    break
                self.trans[y[i, j], y[i, j + 1]] += 1
        self.trans[self.trans == 0.] = self.eps
        self.trans /= self.trans.sum(dim=1, keepdim=True)

        self.obprob[self.obprob == 0.] = self.eps
        self.obprob /= self.obprob.sum(dim=1, keepdim=True)

        self.trans = torch.log(self.trans)
        self.obprob = torch.log(self.obprob)
        self.pi = torch.log(self.pi)

    def decoding(self, seq):
        """
        Given an observation sequence, returning the most likely sequence of states.
        :param seq: observation sequence, shape=[max_len, ]
        :return: (Optimal path, Probability of the optimal path)
        """
        seqlen = seq.shape[0]
        delte = self.pi + self.obprob[:, seq[0]]
        psi = torch.zeros(seqlen, self.pi.shape[0]).long()
        for i in range(1, seqlen):
            tmp = delte + self.trans.t()
            psi[i] = torch.argmax(tmp, dim=1)
            delte = tmp.max(dim=1)[0] + self.obprob[:, seq[i]]
        path = torch.zeros(seqlen).long()
        path[seqlen - 1] = torch.argmax(delte)
        optimal_path_prob = delte[path[seqlen - 1]]
        for t in range(seqlen - 2, -1, -1):
            path[t] = psi[t + 1, path[t + 1]]
        return path, optimal_path_prob

    def predict_one(self, X):
        path, _ = self.decoding(X)
        return path

    def predict(self, X):
        return torch.stack([self.predict_one(seq) for seq in X])

    def save(self, filename):
        pi = self.pi.view(-1, 1)
        mat = torch.cat([pi, self.trans, self.obprob], dim=-1)
        torch.save(mat, filename)

    def load(self, filename):
        mat = torch.load(filename)
        n_status = mat.shape[0]
        self.pi = mat[:, 0]
        self.trans = mat[:, 1:n_status + 1]
        self.obprob = mat[:, n_status + 1:]


class CRFTagger(object):
    def __init__(self):
        pass
