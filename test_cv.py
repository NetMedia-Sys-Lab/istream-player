# Python program to explain cv2.imshow() method

# importing cv2
import asyncio

import cv2


async def main():
    # path
    path = r"/home/akram/Pictures/Screenshot_20221022_172536.png"

    # Reading an image in default mode
    image = cv2.imread(path)

    # Window name in which image is displayed
    window_name = "image"

    print(len(image), len(image[0]), len(image[0][0]))

    # Using cv2.imshow() method
    # Displaying the image
    cv2.imshow(window_name, image)

    # waits for user to press any key
    # (this is necessary to avoid Python kernel form crashing)
    cv2.waitKey(0)

    # closing all open windows
    cv2.destroyAllWindows()



if __name__ == "__main__":
    asyncio.run(main())