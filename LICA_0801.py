from google.colab import drive
drive.mount('/content/drive')

import pandas as pd
import os
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
import cv2
from PIL import Image
from sklearn.utils import class_weight
from sklearn.utils import shuffle

def load_data():
    """
    데이터를 로드하고, 훈련/검증/테스트 세트로 분할하는 함수.

    Returns:
    file_list (list): 전체 파일 리스트.
    labels (numpy.ndarray): 전체 라벨 배열.
    train_files (list): 훈련 세트 파일 리스트.
    test_files (list): 테스트 세트 파일 리스트.
    train_labels (numpy.ndarray): 훈련 세트 라벨 배열.
    test_labels (numpy.ndarray): 테스트 세트 라벨 배열.
    train_files (list): 훈련 세트 파일 리스트.
    val_files (list): 검증 세트 파일 리스트.
    train_labels (numpy.ndarray): 훈련 세트 라벨 배열.
    val_labels (numpy.ndarray): 검증 세트 라벨 배열.
    class_weights (dict): 클래스 가중치 딕셔너리.
    """
    # npy 데이터가 저장된 디렉토리 경로
    file_dir ='/content/drive/MyDrive/aneurysm/data720'

    # .npy 파일 리스트를 생성하고 파일 이름에 따라 오름차순 정렬
    file_list = [os.path.join(file_dir, file) for file in os.listdir(file_dir) if file.endswith('.npy')]
    file_list = sorted(file_list, key=lambda x: int(os.path.splitext(os.path.basename(x))[0]))

    # 레이블 데이터를 불러와 numpy 배열로 변환
    labels = pd.read_csv('/content/drive/MyDrive/aneurysm/train.csv')
    labels = labels['L_ICA'].values

    # 레이블 0과 1의 인덱스를 각각 추출
    idx_0 = np.where(labels == 0)[0] # indices of label 0
    idx_1 = np.where(labels == 1)[0] # indices of label 1
    N = len(idx_1) # Number of data with label 1

    # 검증 세트 + 테스트 세트 생성 (레이블 1의 데이터 개수의 60%를 사용)
    idx_1_val_test = np.random.choice(idx_1, size=int(0.6*N), replace=False) # indices for label 1
    idx_0_val_test = np.random.choice(idx_0, size=int(0.6*N), replace=False) # indices for label 0

    # 검증 세트 + 테스트 세트 인덱스와 파일 리스트, 레이블 생성
    val_test_indices = np.concatenate([idx_1_val_test, idx_0_val_test])
    val_test_files = [file_list[i] for i in val_test_indices]
    val_test_labels = labels[val_test_indices]

    # 검증 세트 + 테스트 세트를 검증 세트와 테스트 세트로 나눔
    val_files, test_files, val_labels, test_labels = train_test_split(val_test_files, val_test_labels, test_size=0.5, random_state=42)

    # 나머지 데이터로 훈련 세트 생성
    train_indices = np.setdiff1d(np.arange(len(labels)), val_test_indices)
    train_files = [file_list[i] for i in train_indices]
    train_labels = labels[train_indices]

    # 훈련 세트에 대한 클래스 가중치 계산
    class_weights = class_weight.compute_class_weight('balanced', classes=np.unique(train_labels), y=train_labels)
    class_weights = dict(enumerate(class_weights))

    # 각 세트의 레이블 개수를 카운트하여 출력
    unique, counts = np.unique(train_labels, return_counts=True)
    print(f"Train labels: {dict(zip(unique, counts))}")

    unique, counts = np.unique(val_labels, return_counts=True)
    print(f"Validation labels: {dict(zip(unique, counts))}")

    unique, counts = np.unique(test_labels, return_counts=True)
    print(f"Test labels: {dict(zip(unique, counts))}")

    return file_list, labels, train_files, val_files, test_files, train_labels, val_labels, test_labels, class_weights

file_list, labels, train_files, val_files, test_files, train_labels, val_labels, test_labels, class_weights = load_data()

print(f'0: {sum(labels==0)}')
print(f'1: {sum(labels==1)}')
print(f'class_weight {class_weights}')

def remove_black_borders(image, threshold):
    """
    이미지에서 검은색 테두리를 제거하는 함수

    Parameters:
    image (numpy.ndarray): 원본 이미지. 2D array로 구성되어 있어야 함.
    threshold (int): 픽셀 값의 임계치. 이 값보다 작거나 같은 픽셀은 검은색으로 간주함.

    Returns:
    image (numpy.ndarray): 검은색 테두리가 제거된 이미지. 2D array.
    """
    # 왼쪽의 검은색 테두리 제거
    while image.shape[1] > 0 and np.average(image[:, 0]) <= threshold:
        image = image[:, 1:]

    # 오른쪽의 검은색 테두리 제거
    while image.shape[1] > 0 and np.average(image[:, -1]) <= threshold:
        image = image[:, :-1]

    # 위쪽의 검은색 테두리 제거
    while image.shape[0] > 0 and np.average(image[0, :]) <= threshold:
        image = image[1:, :]

    # 아래쪽의 검은색 테두리 제거
    while image.shape[0] > 0 and np.average(image[-1, :]) <= threshold:
        image = image[:-1, :]

    return image  # 검은색 테두리가 제거된 이미지를 반환

def pad_image(image, target_shape):
    """
    이미지를 주어진 대상 크기에 맞게 패딩하는 함수

    Parameters:
    image (numpy.ndarray): 원본 이미지. 2D array로 구성되어 있어야 함.
    target_shape (tuple): 패딩 후 원하는 이미지의 크기. (height, width) 형태.

    Returns:
    numpy.ndarray: 주어진 패딩 범위로 패딩이 추가된 이미지. 2D array.
    """
    # y축과 x축에 추가할 패딩 크기 계산
    pad_y = max(0, target_shape[0] - image.shape[0])
    pad_x = max(0, target_shape[1] - image.shape[1])

    # 패딩 크기에 따른 패딩 범위 계산
    pad_width = ((pad_y//2, (pad_y+1)//2), (pad_x//2, (pad_x+1)//2))

    # 주어진 패딩 범위로 이미지에 패딩 추가, 패딩 값은 255 (흰색)
    return np.pad(image, pad_width, mode='constant', constant_values=255)

PIX = 400
channels = 2

def load_and_preprocess(file, label, pix=PIX):
    """
    주어진 파일로부터 이미지를 로드하고, 사전 처리하는 함수

    Parameters:
    file (str): 이미지가 저장된 .npy 파일 경로
    label (int): 해당 이미지의 라벨
    pix (int): 출력 이미지의 픽셀 크기. 기본값은 전역 변수 PIX.

    Returns:
    stacked_imgs (numpy.ndarray): 사전 처리된 이미지. 3D array (pix, pix, 2).
    label (int): 해당 이미지의 라벨.
    """
    imgs = np.load(file)[:, :, :2] #720, 720, 8 -> 720, 720, 2; 'LI-A', 'LI-B' 채널만 필요.
    preprocessed_imgs = []

    for i in range(2): # 채널 수에 따른 루프
        img = imgs[:, :, i]

        img = remove_black_borders(img, threshold = 100) # 검은색 테두리 제거
        img = pad_image(img, (pix, pix)) # 이미지 패딩
        img = cv2.resize(img, (pix, pix))  # 이미지 크기 조정

        img_pil = Image.fromarray(img.astype(np.uint8))  # 이미지를 PIL 객체로 변환
        binarize_threshold = np.percentile(np.array(img_pil), 5)  # 5분위수 계산
        img = img_pil.point(lambda x: 0 if x < binarize_threshold else 255) # 5분위수를 기준으로 이진화
        img = np.array(img)  # 이미지를 다시 numpy array로 변환

        img = 255 - img # 색 반전
        img = img / 255.0  # 정규화 (0 ~ 1 범위로 조정)
        preprocessed_imgs.append(img)

    stacked_imgs = np.stack(preprocessed_imgs)
    stacked_imgs = stacked_imgs.transpose((1, 2, 0))  # (pix, pix, 2)의 형태로 transpose
    return stacked_imgs, label


def npy_generator(file_list, labels, pix=PIX):
    """
    .npy 파일과 라벨로부터 이미지 데이터를 생성하는 제너레이터

    Parameters:
    file_list (list): 이미지가 저장된 .npy 파일 경로들의 리스트
    labels (numpy.ndarray): 각 이미지에 해당하는 라벨들의 배열
    pix (int): 출력 이미지의 픽셀 크기. 기본값은 전역 변수 PIX.

    Yields:
    numpy.ndarray, int: 사전 처리된 이미지와 해당 라벨.
    """
    for file, label in zip(file_list, labels):
        yield load_and_preprocess(file, label, pix)

def get_tf_dataset(batch_size = 8):
    """
    훈련, 검증, 테스트 데이터 세트를 생성하는 함수.

    Args:
    batch_size (int): 배치 크기.

    Returns:
    train_dataset (tf.data.Dataset): 훈련 데이터 세트.
    val_dataset (tf.data.Dataset): 검증 데이터 세트.
    test_dataset (tf.data.Dataset): 테스트 데이터 세트.
    """
    # 훈련 데이터 세트
    train_dataset = tf.data.Dataset.from_generator(
        npy_generator,
        output_signature=(
            tf.TensorSpec(shape=(PIX, PIX, channels), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.int32),
        ),
        args=(train_files, train_labels, PIX)
    )

    # 검증 데이터 세트
    val_dataset = tf.data.Dataset.from_generator(
        npy_generator,
        output_signature=(
            tf.TensorSpec(shape=(PIX, PIX, channels), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.int32),
        ),
        args=(val_files, val_labels, PIX)
    )

    # 테스트 데이터 세트
    test_dataset = tf.data.Dataset.from_generator(
        npy_generator,
        output_signature=(
            tf.TensorSpec(shape=(PIX, PIX, channels), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.int32),
        ),
        args=(test_files, test_labels, PIX)
    )

    AUTOTUNE = tf.data.AUTOTUNE
    BATCH_SIZE = batch_size

    train_dataset = train_dataset.batch(BATCH_SIZE).prefetch(AUTOTUNE)  # 데이터가 랜덤하게 생성되므로 shuffle 필요 없음
    val_dataset = val_dataset.batch(BATCH_SIZE).prefetch(AUTOTUNE)
    test_dataset = test_dataset.batch(BATCH_SIZE).prefetch(AUTOTUNE)

    return train_dataset, val_dataset, test_dataset

train_dataset, val_dataset, test_dataset = get_tf_dataset()

from tensorflow.keras.models import Model, load_model
from tensorflow.keras.layers import Input, Conv2D, MaxPooling2D, Flatten, Dense, BatchNormalization, Activation, add, GlobalAveragePooling2D


def resnet_block(input, channels):
    x = Conv2D(channels, (3, 3), padding='same')(input)
    x = BatchNormalization()(x)
    x = Activation('relu')(x)

    x = Conv2D(channels, (3, 3), padding='same')(x)
    x = BatchNormalization()(x)

    shortcut = Conv2D(channels, (1, 1), padding='same')(input)  # make the same dimension for adding
    shortcut = BatchNormalization()(shortcut)

    x = add([x, shortcut])
    x = Activation('relu')(x)

    return x

# Define the model
input = Input(shape=(PIX, PIX, channels))

# First conv
x = Conv2D(32, (7, 7), strides=2, padding='same')(input)
x = BatchNormalization()(x)
x = Activation('relu')(x)
x = MaxPooling2D((3, 3), strides=2, padding='same')(x)

# ResNet blocks
x = resnet_block(x, 64)
x = resnet_block(x, 128)
x = resnet_block(x, 256)
x = resnet_block(x, 512)

# Final layers
x = Flatten()(x)
x = Dense(1, activation='sigmoid')(x)  # binary classification

model = Model(inputs=input, outputs=x)
model.summary()

model.compile(
    #optimizer = tf.keras.optimizers.legacy.SGD(learning_rate=0.03, decay=1e-6, momentum= 0.9, nesterov = True)
    optimizer = tf.keras.optimizers.Adam(learning_rate=0.001)
    ,
    loss='binary_crossentropy',
    metrics=['accuracy'])

callback = tf.keras.callbacks.EarlyStopping(
    monitor='loss',
    patience=5,
    restore_best_weights=False
)

history = model.fit(train_dataset,
                    epochs=40,
                    callbacks = [callback],
                    validation_data=val_dataset,
                    class_weight = class_weights)

test_loss, test_acc = model.evaluate(test_dataset)
print('Test accuracy:', test_acc)

import matplotlib.pyplot as plt

# Plot training & validation accuracy values
plt.figure(figsize=(12, 4))

plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'])
plt.plot(history.history['val_accuracy'])
plt.title('Model accuracy')
plt.ylabel('Accuracy')
plt.xlabel('Epoch')
plt.legend(['Train', 'Val'], loc='upper left')

# Plot training & validation loss values
plt.subplot(1, 2, 2)
plt.plot(history.history['loss'])
plt.plot(history.history['val_loss'])
plt.title('Model loss')
plt.ylabel('Loss')
plt.xlabel('Epoch')
plt.legend(['Train', 'Val'], loc='upper left')

plt.tight_layout()
plt.show()
