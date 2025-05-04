from PIL import Image

path = input("Enter path:\n")
img = Image.open(path)
img.show()
